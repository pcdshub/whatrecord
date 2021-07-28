from __future__ import annotations

import math
import pathlib
from dataclasses import field
from typing import Dict, List, Optional, Tuple, Union

import lark

from . import transformer
from .common import (DatabaseDevice, DatabaseMenu, FullLoadContext,
                     LinterError, LinterWarning, LoadContext,
                     PVAFieldReference, RecordField, RecordInstance,
                     RecordType, RecordTypeField, StringWithContext, dataclass)
from .macro import MacroContext


def split_record_and_field(pvname) -> Tuple[str, str]:
    """Split REC.FLD into REC and FLD."""
    record, *field = pvname.split(".", 1)
    return record, field[0] if field else ""


@dataclass
class DatabaseBreakTable:
    name: str
    # values: Tuple[str, ...]
    values: List[str]


@dataclass
class DatabaseRecordAlias:
    name: Optional[str]
    alias: str


@dataclass
class DatabaseRecordFieldInfo:
    context: FullLoadContext
    name: str
    value: str


class DatabaseLoadFailure(Exception):
    ...


class UnquotedString(lark.lexer.Token):
    """
    An unquoted string token found when loading a database file.
    May be a linter warning.
    """
    ...


def _separate_by_class(items, mapping):
    """Separate ``items`` by type into ``mapping`` of collections."""
    for item in items:
        container = mapping[type(item)]
        if isinstance(container, list):
            container.append(item)
        else:
            container[item.name] = item


def _context_from_token(fn: str, token: lark.Token) -> FullLoadContext:
    return (LoadContext(name=fn, line=token.line), )


def _pva_q_group_handler(rec, group, md):
    """Handler for Q:group."""

    # record(...) {
    #     info(Q:group, {      # <--- this thing
    #         "<group_name>":{
    #             +id:"some/NT:1.0",
    #             +meta:"FLD",
    #             +atomic:true,
    #             "<field.name>":{
    #                 +type:"scalar",
    #                 +channel:"VAL",
    #                 +id:"some/NT:1.0",
    #                 +trigger:"*",
    #                 +putorder:0,
    #             }
    #         }
    #     })
    # }
    for field_name, field_info in md.items():
        try:
            fieldref = group.fields[field_name]
        except KeyError:
            fieldref = group.fields[field_name] = PVAFieldReference(
                name=str(field_name),
                context=tuple(field_name.context),
            )

        if isinstance(field_info, dict):
            # There, uh, is still some work left to do here.
            channel = field_info.pop("+channel", None)
            if channel is not None:
                fieldref.record_name = rec.name
                fieldref.field_name = channel
                # Linter TODO: checks that this field exists and
                # whatnot

            fieldref.metadata.update(field_info)
        else:
            fieldref.metadata[field_name] = field_info


def _extract_pva_groups(
    records: List[RecordInstance]
) -> Dict[str, RecordInstance]:
    """
    Take a list of ``RecordInstance``, aggregate qsrv "Q:" info nodes, and
    assemble new pseudo-``RecordInstance`` "PVA" out of them.
    """
    pva_groups = {}
    for rec in records:
        group_md = rec.metadata.pop("Q:group", None)
        if group_md is not None:
            for group_name, group_info_to_add in group_md.items():
                try:
                    group = pva_groups[group_name]
                except KeyError:
                    pva_groups[group_name] = group = RecordInstance(
                        context=group_name.context,
                        name=str(group_name),
                        record_type="PVA",
                        is_pva=True,
                    )

                _pva_q_group_handler(rec, group, group_info_to_add)

    return pva_groups


@dataclass
class _TransformerState:
    _record: Optional[RecordInstance] = None
    _record_type: Optional[RecordType] = None

    def reset_record(self):
        """Reset the current record instance."""
        self._record = None

    @property
    def record(self) -> RecordInstance:
        """The current record instance."""
        if self._record is None:
            self._record = RecordInstance(
                context=(),
                name="",
                record_type="",
            )
        return self._record

    def reset_record_type(self):
        """Reset the current record type."""
        self._record_type = None

    @property
    def record_type(self) -> RecordType:
        """The current record type."""
        if self._record_type is None:
            self._record_type = RecordType(
                context=(),
                name="",
            )
        return self._record_type


@lark.visitors.v_args(inline=True)
class _DatabaseTransformer(lark.visitors.Transformer_InPlaceRecursive):
    record: Optional[RecordInstance]
    record_type: Optional[RecordType]

    def __init__(self, fn, dbd=None):
        self.fn = str(fn)
        self.dbd = dbd
        self.db = Database()
        self._state = _TransformerState()

    @property
    def record_types(self) -> Dict[str, RecordType]:
        if self.dbd is not None:
            return self.dbd.record_types
        return self.db.record_types

    @lark.visitors.v_args(tree=True)
    def database(self, body):
        standalone_aliases = []

        # Aggregate the aliases for convenience
        for alias in standalone_aliases:
            self.db.standalone_aliases.append(alias.alias)
            self.db.aliases[alias.alias] = alias.name

        for record in self.db.records.values():
            for alias in record.aliases:
                self.db.aliases[alias] = record.name

        self.db.pva_groups = _extract_pva_groups(self.db.records.values())
        return self.db

    dbitem = transformer.tuple_args

    def include(self, path):
        # raise RuntimeError("Incomplete dbd files are a TODO :(")
        self.db.includes.append(str(path))

    def path(self, path):
        self.db.paths.append(path)

    def addpath(self, path):
        self.db.addpaths.append(path)

    def menu(self, menu_token: lark.Token, name, choices):
        self.db.menus[name] = DatabaseMenu(
            context=_context_from_token(self.fn, menu_token),
            name=name,
            choices=choices
        )

    menu_head = transformer.pass_through
    menu_body = transformer.dictify

    def device(self, _, record_type, link_type, dset_name, choice_string):
        self.db.devices.append(
            DatabaseDevice(record_type, link_type, dset_name, choice_string)
        )

    def driver(self, _, drvet_name):
        self.db.drivers.append(drvet_name)

    def link(self, _, name, identifier):
        self.db.links[name] = identifier

    def registrar(self, _, name):
        self.db.registrars.append(name)

    def function(self, _, name):
        self.db.functions.append(name)

    def variable(self, _, name, value=None):
        self.db.variables[name] = value

    def breaktable(self, _, name, values):
        self.db.breaktables[name] = DatabaseBreakTable(name, values)

    break_head = transformer.pass_through
    break_body = transformer.pass_through
    break_list = transformer.tuple_args
    break_item = transformer.pass_through

    def choice(self, _, identifier, string):
        return (identifier, string)

    def recordtype_field(self, field_tok, head, body):
        name, type_ = head
        known_keys = (
            "asl",
            "base",
            "extra",
            "initial",
            "interest",
            "menu",
            "pp",
            "prompt",
            "promptgroup",
            "prop",
            "size",
            "special",
        )
        kwargs = {
            key: body.pop(key)
            for key in known_keys
            if key in body
        }

        if body:
            # Only add this in if necessary; otherwise we can skip serializing
            # it.
            kwargs["body"] = body

        self._state.record_type.fields[name] = RecordTypeField(
            name=name,
            type=type_,
            context=_context_from_token(self.fn, field_tok),
            **kwargs
        )

    recordtype_head = transformer.pass_through
    recordtype_field_body = transformer.dictify
    recordtype_field_head = transformer.tuple_args
    recordtype_field_item = transformer.tuple_args
    recordtype_field_item_menu = transformer.tuple_args

    def standalone_alias(self, _, record_name, alias_name):
        self.db.standalone_aliases.append(
            DatabaseRecordAlias(record_name, alias_name)
        )

    def json_string(self, value):
        if value and value[0] in "'\"":
            return value[1:-1]
        # return UnquotedString('UnquotedString', str(value))

        # This works okay in practice, I just don't like the repr we get.
        # Not sure if there's a better way to do the same linting functionality
        # as pypdb without it.
        return str(value)

    string = json_string

    def json_key(self, value) -> StringWithContext:
        # Add context information for keys, especially for Q:group info nodes
        return StringWithContext(
            self.json_string(value),
            context=_context_from_token(self.fn, value),
        )

    def json_array(self, elements=None):
        return elements or []

    def json_elements(self, *elements):
        return elements

    def JSON_TRUE(self, _):
        return True

    def JSON_FALSE(self, _):
        return False

    def JSON_NULL(self, _):
        return None

    def nan(self):
        return math.nan

    def hexint(self, sign, _, digits):
        return f"{sign}0x{digits}"

    def cdef(self, cdef_text):
        self._state.record_type.cdefs.append(str(cdef_text)[1:].strip())

    def recordtype(self, recordtype_token, name, body):
        record_type = self._state.record_type
        record_type.context = _context_from_token(self.fn, recordtype_token)
        record_type.name = name
        self.db.record_types[name] = self._state.record_type
        self._state.reset_record_type()

    def record(self, rec_token, head, body):
        record_type, name = head
        record = self._state.record
        record.name = name
        record.context = _context_from_token(self.fn, rec_token)
        record.is_grecord = rec_token == "grecord"
        record.is_pva = False
        record.record_type = record_type
        self.db.records[name] = self._state.record

        record_type_info = self.record_types.get(
            record.record_type, None
        )
        if record_type_info is None:
            # TODO lint error, if dbd loaded
            ...
        else:
            for fld in record.fields.values():
                field_info = record_type_info.fields.get(fld.name, None)
                if field_info is None:
                    # TODO lint error, if dbd loaded
                    ...
                else:
                    fld.dtype = field_info.type
                    # TODO: not 100% sure about the value of retaining the
                    # script name + line number in every field just yet;
                    # know for certain it's a waste of memory and repetetive
                    # data being sent over the wire at the very least
                    # fld.context = field_info.context[:1] + fld.context
        self._state.reset_record()

    json_dict = transformer.dictify
    json_key_value = transformer.tuple_args
    record_head = transformer.tuple_args

    def record_field(self, field_token, name, value):
        self._state.record.fields[name] = RecordField(
            dtype='', name=name, value=value,
            context=_context_from_token(self.fn, field_token)
        )

    def record_field_info(self, info_token, name, value):
        context = _context_from_token(self.fn, info_token)
        key = StringWithContext(name, context)
        self._state.record.metadata[key] = value

    def record_field_alias(self, _, name):
        self._state.record.aliases.append(name)

    record_body = transformer.tuple_args


@dataclass
class Database:
    """
    Representation of an EPICS database, database definition, or both.

    Attributes
    ----------
    standalone_aliases
        Standalone aliases are those defined outside of the record body; this
        may only be useful for faithfully reconstructing the Database according
        to its original source code.

    aliases
        Alias name to record name.

    paths
    addpaths
        The path command specifies the current search path for use when loading
        database and database definition files. The addpath appends directory
        names to the current path. The path is used to locate the initial
        database file and included files. An empty dir at the beginning,
        middle, or end of a non-empty path string means the current directory.

    breaktables
        Breakpoint table (look-up table) of raw-to-engineering values.

    comments
        Comments encountered while parsing the database.

    devices
        Device support declarations (dset).

    drivers
        Driver declarations (drvet).

    functions
        Exported C function names.

    includes
        Inline inclusion. Not supported just yet.

    links

    menus
        Named value enumerations (enums).

    records
        Record name to RecordInstance.

    record_types
        Record type name to RecordType.

    registrars
        Exported registrar function name.

    variables
        IOC shell variables.
    """

    standalone_aliases: List[str] = field(default_factory=list)
    aliases: Dict[str, str] = field(default_factory=dict)
    paths: List[str] = field(default_factory=list)
    addpaths: List[str] = field(default_factory=list)
    breaktables: Dict[str, DatabaseBreakTable] = field(default_factory=dict)
    comments: List[str] = field(default_factory=list)
    devices: List[DatabaseDevice] = field(default_factory=list)
    drivers: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    links: Dict[str, str] = field(default_factory=dict)
    menus: Dict[str, DatabaseMenu] = field(default_factory=dict)
    records: Dict[str, RecordInstance] = field(default_factory=dict)
    pva_groups: Dict[str, RecordInstance] = field(default_factory=dict)
    record_types: Dict[str, RecordType] = field(default_factory=dict)
    registrars: List[str] = field(default_factory=list)
    variables: Dict[str, Optional[str]] = field(default_factory=dict)

    @classmethod
    def from_string(cls, contents, dbd=None, filename=None,
                    macro_context=None, version: int = 4, include_aliases=True) -> Database:
        comments = []
        grammar = lark.Lark.open_from_package(
            "whatrecord",
            f"db.v{version}.lark",
            search_paths=("grammar", ),
            parser="lalr",
            lexer_callbacks={"COMMENT": comments.append},
            transformer=_DatabaseTransformer(filename, dbd=dbd),
            # Per-user `gettempdir` caching of the LALR grammar analysis way of
            # passing ``True`` here:
            cache=True,
        )
        if macro_context is not None:
            contents = "\n".join(
                macro_context.expand(line) for line in contents.splitlines()
            )
            contents = contents.rstrip() + "\n"

        db = grammar.parse(contents)
        db.comments = comments

        if include_aliases:
            for record_name, record in list(db.records.items()):
                for alias in record.aliases:
                    db.records[alias] = record

        return db

    @classmethod
    def from_file_obj(cls, fp, dbd=None, macro_context=None, version: int = 4) -> Database:
        return cls.from_string(
            fp.read(),
            filename=getattr(fp, "name", None),
            dbd=dbd,
            macro_context=macro_context,
            version=version,
        )

    @classmethod
    def from_file(cls, fn, dbd=None, macro_context=None, version: int = 4) -> Database:
        with open(fn, "rt") as fp:
            return cls.from_string(fp.read(), filename=fn, dbd=dbd,
                                   macro_context=macro_context, version=version)


@dataclass(repr=False)
class LinterResults:
    """
    Container for dbdlint results, with easier-to-access attributes.

    Reimplementation of ``pyPDB.dbdlint.Results``.

    Each error or warning has dictionary keys::

        {name, message, file, line, raw_message, format_args}

    Attributes
    ----------
    errors : list
        List of errors found
    warnings : list
        List of warnings found
    """

    # Validate as complete database
    whole: bool = False

    # Set if some syntax/sematic error is encountered
    error: bool = False
    warning: bool = False

    # {'ao':{'OUT':'DBF_OUTLINK', ...}, ...}
    record_types: Dict[str, RecordType] = field(default_factory=dict)

    # {'ao':{'Soft Channel':'CONSTANT', ...}, ...}
    # recdsets: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # {'inst:name':'ao', ...}
    records: Dict[str, RecordInstance] = field(default_factory=dict)
    pva_groups: Dict[str, RecordInstance] = field(default_factory=dict)

    extinst: List[str] = field(default_factory=list)
    errors: List[LinterError] = field(default_factory=list)
    warnings: List[LinterWarning] = field(default_factory=list)

    # Records with context and field information:
    records: Dict[str, RecordInstance] = field(default_factory=dict)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"records={len(self.records)} "
            f"errors={len(self.errors)} "
            f"warnings={len(self.warnings)} "
            f">"
        )

    def _record_warning_or_error(self, category, name, msg, args):
        target_list, cls = {
            "warning": (self.warnings, LinterWarning),
            "error": (self.errors, LinterError),
        }[category]
        target_list.append(
            cls(
                name=name,
                file=str(self.node.fname),
                line=self.node.lineno,
                message=msg % args,
            )
        )

    def err(self, name, msg, *args):
        self._error = True
        self._record_warning_or_error("error", name, msg, args)

    def warn(self, name, msg, *args):
        if name in self.warn_options:
            self._warning = True
        self._record_warning_or_error("warning", name, msg, args)

    @property
    def success(self):
        """
        Returns
        -------
        success : bool
            True if the linting process succeeded without errors
        """
        return not len(self.errors)


def load_database_file(
    dbd: Union[Database, str, pathlib.Path],
    db: Union[str, pathlib.Path],
    macro_context: Optional[MacroContext] = None,
    *,
    version: int = 3,
    full: bool = True,
    warn_ext_links: bool = False,
    warn_bad_fields: bool = True,
    warn_rec_append: bool = False,
    warn_quoted: bool = False,
    warn_varint: bool = True,
    warn_spec_comm: bool = True,
):
    """
    Lint a db (database) file using its database definition file (dbd) using
    pyPDB.

    Parameters
    ----------
    dbd : Database or str
        The database definition file; filename or pre-loaded Database
    db : str
        The database filename.
    version : int, optional
        Use the old V3 style or new V3 style database grammar by specifying
        3 or 4, respectively.  Defaults to 3.
    full : bool, optional
        Validate as a complete database
    warn_quoted : bool, optional
        A node argument isn't quoted
    warn_varint : bool, optional
        A variable(varname) node which doesn't specify a type, which defaults
        to 'int'
    warn_spec_comm : bool, optional
        Syntax error in special #: comment line
    warn_ext_link : bool, optional
        A DB/CA link to a PV which is not defined.  Add '#: external("pv.FLD")
    warn_bad_field : bool, optional
        Unable to validate record instance field due to a previous error
        (missing recordtype).
    warn_rec_append : bool, optional
        Not using Base >=3.15 style recordtype "*" when appending/overwriting
        record instances

    Raises
    ------
    DBSyntaxError
        When a syntax issue is discovered. Note that this exception contains
        file and line number information (attributes: fname, lineno, results)

    Returns
    -------
    results : LinterResults
    """
    if isinstance(dbd, Database):
        dbd = dbd
    else:
        dbd = Database.from_file(dbd, version=version)

    db = Database.from_file(
        db, dbd=dbd, macro_context=macro_context, version=version
    )

    # all TODO
    return LinterResults(
        record_types=dbd.record_types,
        # {'ao':{'Soft Channel':'CONSTANT', ...}, ...}
        # recdsets=dbd.devices,  # TODO
        # {'inst:name':'ao', ...}
        records=db.records,
        pva_groups=db.pva_groups,
        extinst=[],
        errors=[],
        warnings=[],
    )
