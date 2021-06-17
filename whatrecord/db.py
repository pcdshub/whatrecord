from __future__ import annotations

import os
import pathlib
from dataclasses import field
from typing import Dict, List, Optional, Tuple, Union

import lark

from whatrecord.common import (FullLoadContext, LinterError, LinterWarning,
                               LoadContext, PVAFieldReference, RecordField,
                               RecordInstance, StringWithContext, dataclass)
from whatrecord.macro import MacroContext

# TODO: change back to relative imports


MAX_RECORD_LENGTH = int(os.environ.get("EPICS_MAX_RECORD_LENGTH", "60"))


def split_record_and_field(pvname) -> Tuple[str, str]:
    """Split REC.FLD into REC and FLD."""
    record, *field = pvname.split(".", 1)
    return record, field[0] if field else ""


@dataclass
class RecordTypeField:
    name: str
    type: str
    body: List[Tuple[str, str]]
    context: FullLoadContext


@dataclass
class RecordTypeCdef:
    text: str


@dataclass
class DatabaseMenu:
    name: str
    choices: Dict[str, str]


@dataclass
class DatabaseInclude:
    path: str


@dataclass
class DatabasePath:
    path: str


@dataclass
class DatabaseAddPath:
    path: str


@dataclass
class DatabaseDriver:
    drvet_name: str


@dataclass
class DatabaseLink:
    name: str
    identifier: str


@dataclass
class DatabaseRegistrar:
    function_name: str


@dataclass
class DatabaseFunction:
    function_name: str


@dataclass
class DatabaseVariable:
    name: str
    data_type: Optional[str]


@dataclass
class DatabaseDevice:
    record_type: str
    link_type: str
    dset_name: str
    choice_string: str


@dataclass
class DatabaseBreakTable:
    name: str
    values: List[Tuple[str, ...]]


@dataclass
class DatabaseRecordAlias:
    record_name: Optional[str]
    alias_name: str


@dataclass
class DatabaseRecordFieldInfo:
    context: FullLoadContext
    name: str
    value: str


@dataclass
class RecordType:
    name: str
    cdefs: List[str]
    fields: Dict[str, RecordTypeField]
    devices: Dict[str, DatabaseDevice] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    info: Dict[str, str] = field(default_factory=dict)
    is_grecord: bool = False


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


@lark.visitors.v_args(inline=True)
class _DatabaseTransformer(lark.visitors.Transformer_InPlaceRecursive):
    def __init__(self, fn, dbd=None):
        self.fn = str(fn)
        self.dbd = dbd
        self.record_types = dbd.record_types if dbd is not None else {}

    @lark.visitors.v_args(tree=True)
    def database(self, body):
        db = Database()
        _separate_by_class(
            body.children,
            {
                DatabaseMenu: db.menus,
                DatabaseInclude: db.includes,
                DatabasePath: db.paths,
                DatabaseAddPath: db.addpaths,
                DatabaseDriver: db.drivers,
                DatabaseLink: db.links,
                DatabaseRegistrar: db.registrars,
                DatabaseFunction: db.functions,
                DatabaseVariable: db.variables,
                DatabaseRecordAlias: db.standalone_aliases,

                RecordType: db.record_types,
                DatabaseBreakTable: db.breaktables,
                RecordInstance: db.records,
                DatabaseDevice: db.devices,
            }
        )

        db.pva_groups = _extract_pva_groups(db.records.values())
        return db

    def dbitem(self, *items):
        return items

    def include(self, path):
        # raise RuntimeError("Incomplete dbd files are a TODO :(")
        return DatabaseInclude(path)

    def path(self, path):
        return DatabasePath(path)

    def addpath(self, path):
        return DatabaseAddPath(path)

    def menu(self, _, name, choices):
        return DatabaseMenu(name=name, choices=choices)

    def menu_head(self, name):
        return name

    def menu_body(self, *choices):
        return dict(choices)

    def device(self, _, record_type, link_type, dset_name, choice_string):
        return DatabaseDevice(record_type, link_type, dset_name, choice_string)

    def driver(self, _, drvet_name):
        return DatabaseDriver(drvet_name)

    def link(self, _, name, identifier):
        return DatabaseLink(name, identifier)

    def registrar(self, _, name):
        return DatabaseRegistrar(name)

    def function(self, _, name):
        return DatabaseFunction(name)

    def variable(self, _, name, value=None):
        return DatabaseVariable(name, value)

    def breaktable(self, _, name, values):
        return DatabaseBreakTable(name, values)

    def break_head(self, name):
        return name

    def break_body(self, items):
        return items

    def break_list(self, *items):
        return items

    def break_item(self, value):
        return value

    def choice(self, _, identifier, string):
        return (identifier, string)

    def recordtype_field(self, field_tok, head, body):
        name, type_ = head
        return RecordTypeField(
            name=name, type=type_, body=body,
            context=_context_from_token(self.fn, field_tok)
        )

    def recordtype_head(self, head):
        return head

    # @lark.visitors.v_args(tree=True)
    def recordtype_field_body(self, *items):
        return items

    def recordtype_field_head(self, name, type_):
        return (name, type_)

    def recordtype_field_item(self, name, value):
        return (name, value)

    def alias(self, _, alias_name):
        return DatabaseRecordAlias(None, alias_name)

    def standalone_alias(self, _, record_name, alias_name):
        return DatabaseRecordAlias(record_name, alias_name)

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

    def json_array(self, elements):
        return elements

    def json_elements(self, elements):
        return elements

    recordtype_field_item_menu = recordtype_field_item

    def cdef(self, cdef_text):
        return RecordTypeCdef(cdef_text)

    def recordtype(self, _, name, body):
        info = {
            RecordTypeCdef: [],
            RecordTypeField: {},
        }
        _separate_by_class(body.children, info)
        record_type = RecordType(
            name=name,
            fields=info[RecordTypeField],
            cdefs=[cdef.text for cdef in info[RecordTypeCdef]],
        )
        self.record_types[name] = record_type
        return record_type

    def record(self, rec_token, head, body):
        record_type, name = head
        info = {
            RecordField: {},
            DatabaseRecordFieldInfo: {},
            DatabaseRecordAlias: [],
        }
        _separate_by_class(body, info)

        record_type_info = self.record_types.get(record_type, None)
        if record_type_info is None:
            # TODO lint error, if dbd loaded
            ...
        else:
            for fld in info[RecordField].values():
                field_info = record_type_info.fields.get(fld.name, None)
                if field_info is None:
                    # TODO lint error, if dbd loaded
                    ...
                else:
                    fld.dtype = field_info.type
                    fld.context = field_info.context + fld.context

        return RecordInstance(
            aliases=[alias.alias_name for alias in info[DatabaseRecordAlias]],
            context=_context_from_token(self.fn, rec_token),
            fields=info[RecordField],
            is_grecord=(rec_token == "grecord"),
            is_pva=False,
            metadata={
                StringWithContext(item.name, item.context): item.value
                for item in info[DatabaseRecordFieldInfo].values()
            },
            name=name,
            record_type=record_type,
        )

    def json_dict(self, *members):
        return dict(members)

    def json_key_value(self, key, value):
        return (key, value)

    def record_head(self, record_type, name):
        return (record_type, name)

    def record_field(self, field_token, name, value):
        return RecordField(
            dtype='', name=name, value=value,
            context=_context_from_token(self.fn, field_token)
        )

    def record_field_info(self, info_token, name, value):
        return DatabaseRecordFieldInfo(
            context=_context_from_token(self.fn, info_token),
            name=name, value=value,
        )

    def record_field_alias(self, _, name):
        return DatabaseRecordAlias(None, name)

    def record_body(self, *body_items):
        return body_items


@dataclass
class Database:
    standalone_aliases: List[DatabaseRecordAlias] = field(default_factory=list)
    addpaths: List[DatabaseAddPath] = field(default_factory=list)
    breaktables: Dict[str, DatabaseBreakTable] = field(default_factory=dict)
    comments: List[str] = field(default_factory=list)
    devices: List[DatabaseDevice] = field(default_factory=list)
    drivers: List[DatabaseDriver] = field(default_factory=list)
    functions: List[DatabaseFunction] = field(default_factory=list)
    includes: List[DatabaseInclude] = field(default_factory=list)
    links: List[DatabaseLink] = field(default_factory=list)
    menus: List[DatabaseMenu] = field(default_factory=list)
    paths: List[DatabasePath] = field(default_factory=list)
    records: Dict[str, RecordInstance] = field(default_factory=dict)
    pva_groups: Dict[str, RecordInstance] = field(default_factory=dict)
    record_types: Dict[str, RecordType] = field(default_factory=dict)
    registrars: List[DatabaseRegistrar] = field(default_factory=list)
    variables: List[DatabaseVariable] = field(default_factory=list)

    @classmethod
    def from_string(cls, contents, dbd=None, filename=None,
                    macro_context=None) -> Database:
        comments = []
        grammar = lark.Lark.open_from_package(
            "whatrecord", "db.lark", search_paths=("grammar", ),
            parser="lalr",
            lexer_callbacks={"COMMENT": comments.append},
            transformer=_DatabaseTransformer(filename, dbd=dbd),
            # Caches LALR grammar analysis to a local file:
            # TODO: handle cache paths ourselves
            cache='db.lark.cache',
        )
        if macro_context is not None:
            contents = "\n".join(
                macro_context.expand(line) for line in contents.splitlines()
            )
            contents = contents.rstrip() + "\n"

        db = grammar.parse(contents)
        db.comments = comments
        return db

    @classmethod
    def from_file_obj(cls, fp, dbd=None, macro_context=None) -> Database:
        return cls.from_string(
            fp.read(),
            filename=getattr(fp, "name", None),
            dbd=dbd,
            macro_context=macro_context,
        )

    @classmethod
    def from_file(cls, fn, dbd=None, macro_context=None) -> Database:
        with open(fn, "rt") as fp:
            return cls.from_string(fp.read(), filename=fn, dbd=dbd,
                                   macro_context=macro_context)


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
    dbd = dbd if isinstance(dbd, Database) else Database.from_file(dbd)
    db = Database.from_file(db, dbd=dbd, macro_context=macro_context)

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
