from __future__ import annotations

import math
import pathlib
from dataclasses import field
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import apischema
import lark

from . import transformer
from .common import (DatabaseDevice, DatabaseMenu, LinterError, LinterWarning,
                     PVAFieldReference, RecordField, RecordInstance,
                     RecordType, RecordTypeField, StringWithContext, dataclass)
from .macro import MacroContext
from .transformer import context_from_token


def split_record_and_field(pvname) -> Tuple[str, str]:
    """Split REC.FLD into REC and FLD."""
    record, *field = pvname.split(".", 1)
    return record, field[0] if field else ""


class DatabaseLoadFailure(Exception):
    ...


class UnquotedString(str):
    """
    An unquoted string token found when loading a database file.
    May be a linter warning.
    """
    ...


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

    macros: Dict[str, str] = field(default_factory=dict)
    errors: List[LinterError] = field(default_factory=list)
    warnings: List[LinterWarning] = field(default_factory=list)
    db: Optional[Database] = field(
        default=None, metadata=apischema.metadata.skip
    )
    dbd: Optional[Database] = field(
        default=None, metadata=apischema.metadata.skip
    )

    @classmethod
    def from_database_string(
        cls,
        db: str,
        dbd: Optional[Database] = None,
        macro_context: Optional[MacroContext] = None,
        *,
        db_filename: Optional[Union[str, pathlib.Path]] = None,
        version: int = 3,
    ) -> LinterResults:
        """
        Lint a db (database) file using its database definition file (dbd).

        Parameters
        ----------
        db : str
            The database source.
        dbd : Database
            The pre-loaded database definition.

        Returns
        -------
        results : LinterResults
        """
        lint = cls()
        if dbd and not isinstance(dbd, Database):
            raise ValueError("dbd should be a Database instance")

        db = Database.from_string(
            db, dbd=dbd, macro_context=macro_context, version=version,
            lint=lint, filename=db_filename
        )
        lint.macros = dict(macro_context or {})
        return lint

    @classmethod
    def from_database_file(
        cls,
        db_filename: Union[str, pathlib.Path],
        dbd: Optional[Database] = None,
        macro_context: Optional[MacroContext] = None,
        *,
        version: int = 3,
    ) -> LinterResults:
        """
        Lint a db (database) file using its database definition file (dbd).

        Parameters
        ----------
        db : str
            The database filename.
        dbd : Database
            The database definition.
        version : int, optional
            Use the old V3 style or new V3 style database grammar by specifying
            3 or 4, respectively.  Defaults to 3.

        Returns
        -------
        results : LinterResults
        db : Database
        """
        with open(db_filename, "rt") as fp:
            db = fp.read()

        return cls.from_database_string(
            db=db,
            dbd=dbd,
            db_filename=db_filename,
            macro_context=macro_context,
            version=version,
        )

    @property
    def record_types(self) -> Optional[Dict[str, RecordType]]:
        """Defined record types."""
        if self.dbd is not None:
            return self.dbd.record_types
        return self.db.record_types if self.db is not None else {}

    @property
    def records(self) -> Optional[Dict[str, RecordInstance]]:
        """Defined V3 records."""
        return self.db.records if self.db is not None else {}

    @property
    def pva_groups(self) -> Optional[Dict[str, RecordInstance]]:
        """Defined PVAccess groups."""
        return self.db.pva_groups if self.db is not None else {}

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"records={len(self.records)} "
            f"pva_groups={len(self.pva_groups)} "
            f"errors={len(self.errors)} "
            f"warnings={len(self.warnings)} "
            f">"
        )


@dataclass
class _TransformerState:
    lint: Optional[LinterResults] = field(default_factory=LinterResults)
    _record: Optional[RecordInstance] = None
    _record_type: Optional[RecordType] = None
    standalone_aliases: Dict[str, str] = field(default_factory=dict)
    aliases_to_update: List[Tuple[RecordInstance, str]] = field(
        default_factory=list
    )
    pva_references_to_update: List[Tuple[RecordInstance, PVAFieldReference]] = field(
        default_factory=list
    )
    # Record names aren't known until after all their fields are processed,
    # so use a magic token here for now.  If this leaks out, that's a bug!
    unset_name: str = "_whatrecord_processing_"

    def reset_record(self):
        """Reset the current record instance."""
        self._record = None

    @property
    def record(self) -> RecordInstance:
        """The current record instance."""
        if self._record is None:
            self._record = RecordInstance(
                context=(),
                name=self.unset_name,
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
    lint: Optional[LinterResults]

    def __init__(self, fn, dbd=None, lint=None):
        self.fn = str(fn)
        self.dbd = dbd
        self.db = Database()
        self._state = _TransformerState(lint=lint or LinterResults())

        self.lint = self._state.lint
        self.lint.db = self.db
        self.lint.dbd = self.dbd

    @property
    def record_types(self) -> Dict[str, RecordType]:
        if self.dbd is not None:
            return self.dbd.record_types
        return self.db.record_types

    @lark.visitors.v_args(tree=True)
    def database(self, body) -> Tuple[Database, LinterResults]:
        # Update all references that were set before we know the record name
        # Update record() { alias("") }
        for record, alias in self._state.aliases_to_update:
            self.db.aliases[alias] = record.name

        # Update pva Q:group field references
        for record, reference in self._state.pva_references_to_update:
            reference.record_name = record.name

        # Update top-level standalone aliases
        for alias_name, record_name in self._state.standalone_aliases.items():
            self.db.standalone_aliases[alias_name] = record_name
            self.db.aliases[alias_name] = record_name
            if record_name in self.db.records:
                self.db.records[record_name].aliases.append(alias_name)
            # else:  linter error

        return self.db, self.lint

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
            context=context_from_token(self.fn, menu_token),
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
        self.db.breaktables[name] = values

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
            context=context_from_token(self.fn, field_tok),
            **kwargs
        )

    recordtype_head = transformer.pass_through
    recordtype_field_body = transformer.dictify
    recordtype_field_head = transformer.tuple_args
    recordtype_field_item = transformer.tuple_args
    recordtype_field_item_menu = transformer.tuple_args

    def standalone_alias(self, _, record_name, alias_name):
        self._state.standalone_aliases[alias_name] = record_name

    def unquoted_string(self, value):
        return UnquotedString(value)

    def json_string(self, value):
        if value and value[0] in "'\"":
            return value[1:-1]
        return UnquotedString(value)

        # This works okay in practice, I just don't like the repr we get.
        # Not sure if there's a better way to do the same linting functionality
        # as pypdb without it.
        return str(value)

    string = json_string

    def json_key(self, value) -> StringWithContext:
        # Add context information for keys, especially for Q:group info nodes
        return StringWithContext(
            self.json_string(value),
            context=context_from_token(self.fn, value),
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
        record_type.context = context_from_token(self.fn, recordtype_token)
        record_type.name = name
        self.db.record_types[name] = self._state.record_type
        self._state.reset_record_type()

    def record(self, rec_token, head, body):
        record_type, name = head
        record = self._state.record
        record.name = name
        record.context = context_from_token(self.fn, rec_token)
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

    def record_field(self, field_token: lark.Token, name: str, value: Any):
        if isinstance(value, UnquotedString):
            self.lint.warnings.append(
                LinterWarning(
                    name="unquoted_field",
                    line=field_token.line,
                    message=f"Unquoted field value {name!r}"
                ),
            )

        self._state.record.fields[name] = RecordField(
            dtype='', name=name, value=value,
            context=context_from_token(self.fn, field_token)
        )

    def _pva_q_group_handler(self, group: RecordInstance, md: Mapping):
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
                    # The current record doesn't have its name yet due to how
                    # the parser goes depth first; update it later.
                    self._state.pva_references_to_update.append(
                        (self._state.record, fieldref)
                    )
                    fieldref.field_name = channel
                    # Linter TODO: checks that this field exists and
                    # whatnot

                fieldref.metadata.update(field_info)
            else:
                fieldref.metadata[field_name] = field_info

    def _add_q_group(self, group_md: Mapping):
        """
        Handle qsrv "Q:" info nodes, and assemble new pseudo-record
        PVA ``RecordInstance`` out of them.
        """
        for group_name, group_info_to_add in group_md.items():
            if group_name not in self.db.pva_groups:
                self.db.pva_groups[group_name] = RecordInstance(
                    context=group_name.context,
                    name=str(group_name),
                    record_type="PVA",
                    is_pva=True,
                )

            self._pva_q_group_handler(
                self.db.pva_groups[group_name],
                group_info_to_add
            )

    def record_field_info(self, info_token: lark.Token, name: str, value: Any):
        record: RecordInstance = self._state.record
        context = context_from_token(self.fn, info_token)
        key = StringWithContext(name, context)
        record.info[key] = value

        if name == "Q:group" and isinstance(value, Mapping):
            self._add_q_group(value)

    def record_field_alias(self, _, name):
        record = self._state.record
        record.aliases.append(name)
        self._state.aliases_to_update.append((record, name))

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
        to its original source code.  Keyed on alias to actual record name.

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

    standalone_aliases: Dict[str, str] = field(default_factory=dict)
    aliases: Dict[str, str] = field(default_factory=dict)
    paths: List[str] = field(default_factory=list)
    addpaths: List[str] = field(default_factory=list)
    breaktables: Dict[str, Tuple[str]] = field(default_factory=dict)
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
    def from_string(
        cls,
        contents: str,
        dbd: Optional[Union[Database, str, pathlib.Path]] = None,
        filename: Union[str, pathlib.Path] = None,
        macro_context: Optional[MacroContext] = None,
        version: int = 4,
        include_aliases: bool = True,
        lint: Optional[LinterResults] = None,
    ) -> Database:
        """Load a database [definition] from a string."""
        if dbd is not None and not isinstance(dbd, Database):
            dbd = Database.from_file(dbd, version=version)

        comments = []
        grammar = lark.Lark.open_from_package(
            "whatrecord",
            f"db.v{version}.lark",
            search_paths=("grammar", ),
            parser="lalr",
            lexer_callbacks={"COMMENT": comments.append},
            transformer=_DatabaseTransformer(filename, dbd=dbd, lint=lint),
            # Per-user `gettempdir` caching of the LALR grammar analysis way of
            # passing ``True`` here:
            cache=True,
        )
        if macro_context is not None:
            contents = macro_context.expand_by_line(contents).rstrip() + "\n"

        db, linter_results = grammar.parse(contents)
        db.comments = comments

        if include_aliases:
            for record_name, record in list(db.records.items()):
                for alias in record.aliases:
                    db.records[alias] = record

        return db

    @classmethod
    def from_file_obj(
        cls, fp,
        dbd: Optional[Union[Database, str, pathlib.Path]] = None,
        filename: Union[str, pathlib.Path] = None,
        macro_context: Optional[MacroContext] = None,
        version: int = 4,
        lint: Optional[LinterResults] = None,
    ) -> Database:
        """Load a database [definition] from a file object."""
        return cls.from_string(
            fp.read(),
            filename=filename or getattr(fp, "name", None),
            dbd=dbd,
            macro_context=macro_context,
            version=version,
            lint=lint,
        )

    @classmethod
    def from_file(
        cls,
        fn: Union[str, pathlib.Path],
        dbd: Optional[Union[Database, str, pathlib.Path]] = None,
        filename: Union[str, pathlib.Path] = None,
        macro_context: Optional[MacroContext] = None,
        version: int = 4,
        lint: Optional[LinterResults] = None,
    ) -> Database:
        """Load a database [definition] from a filename."""
        with open(fn, "rt") as fp:
            return cls.from_string(
                fp.read(),
                filename=fn,
                dbd=dbd,
                macro_context=macro_context,
                version=version,
                lint=lint,
            )
