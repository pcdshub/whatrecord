import copy
import dataclasses
import os
import pathlib
from typing import ClassVar, Dict, Optional, Union

import pyPDB.dbd.yacc as _yacc
import pyPDB.dbdlint as _dbdlint
from pyPDB.dbdlint import DBSyntaxError

from .macro import MacroContext

MAX_RECORD_LENGTH = int(os.environ.get("EPICS_MAX_RECORD_LENGTH", "60"))


@dataclasses.dataclass
class RecordField:
    dtype: str
    name: str
    value: str
    context: tuple

    _jinja_format_: ClassVar[dict] = {
        "console": """field({{name}}, "{{value}}")""",
        "console-verbose": """\
field({{name}}, "{{value}}")  # {{dtype}}{% if context %}; {{context[-1]}}{% endif %}\
"""
    }


@dataclasses.dataclass
class RecordInstance:
    context: tuple
    name: str
    record_type: str
    fields: Dict[str, RecordField]

    _jinja_format_: ClassVar[dict] = {
        "console": """\
record("{{record_type}}", "{{name}}") {
{% for ctx in context %}
    # {{ctx}}
{% endfor %}
{% for name, field_inst in fields.items() | sort %}
{% set field_text = render_object(field_inst, "console") %}
    {{ field_text | indent(4)}}
{% endfor %}
}
""",

    }

    def get_fields_of_type(self, *types):
        """Get all fields of the matching type(s)."""
        for field in self.fields.values():
            if field.dtype in types:
                yield field


def _whole_rec_inst_field(ent, results, info):
    res = _dbdlint.wholeRecInstField(ent, results, info)
    recent, field_name = results.stack[-1], ent.args[0]
    if hasattr(recent, '_fieldinfo'):
        record_type = recent.args[0]
        record_name = recent.args[1]
        ftype = recent._fieldinfo.get(field_name)
        value = ent.args[1]
        results._record_field_defined_by_node(
            node=ent, record_type=record_type, record_name=record_name,
            field_name=field_name, field_type=ftype, value=value
        )

    return res


def _whole_rec_inst(ent, results, info):
    res = _dbdlint.wholeRecInst(ent, results, info)
    rtype = ent.args[0]
    name = ent.args[1]
    appending = rtype == "*"
    if appending and name in results.recinst:
        rtype = results.recinst[name]

    results._record_defined_by_node(node=ent, rtype=rtype, name=name)
    return res


# Patch in some of our own hooks to get additional metadata
dbdtree = copy.deepcopy(_dbdlint.dbdtree)
dbdtree[_dbdlint.Block]["record"]["tree"][_dbdlint.Block]["field"]["wholefn"] = _whole_rec_inst_field  # noqa: E501
dbdtree[_dbdlint.Block]["record"]["wholefn"] = _whole_rec_inst


class LinterResults(_dbdlint.Results):
    """
    Container for dbdlint results, with easier-to-access attributes

    Extends pyPDB.dbdlint.Results

    Each error or warning has dictionary keys::

        {name, message, file, line, raw_message, format_args}

    Attributes
    ----------
    errors : list
        List of errors found
    warnings : list
        List of warnings found
    """

    def __init__(self, args):
        super().__init__(args)
        self.errors = []
        self.warnings = []
        # Records with context and field information:
        self.records = {}

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"records={len(self.recinst)} "
            f"errors={len(self.errors)} "
            f"warnings={len(self.warnings)} "
            f">"
        )

    def _record_warning_or_error(self, result_list, name, msg, args):
        result_list.append(
            {
                "name": name,
                "message": msg % args,
                "file": self.node.fname,
                "line": self.node.lineno,
                "raw_message": msg,
                "format_args": args,
            }
        )

    def _record_field_defined_by_node(self, node, record_type, record_name,
                                      field_name, field_type, value):
        self.records[record_name].fields[field_name] = RecordField(
            dtype=field_type,
            value=value,
            name=field_name,
            context=(f"{node.fname}:{node.lineno}", ),
        )

    def _record_defined_by_node(self, node, name, rtype):
        self.records[name] = RecordInstance(
            context=(f"{node.fname}:{node.lineno}", ),
            name=name,
            record_type=rtype,
            fields={},
        )

    def err(self, name, msg, *args):
        super().err(name, msg, *args)
        self._record_warning_or_error(self.errors, name, msg, args)

    def warn(self, name, msg, *args):
        super().warn(name, msg, *args)
        if name in self._warns:
            self._record_warning_or_error(self.warnings, name, msg, args)

    @property
    def success(self):
        """
        Returns
        -------
        success : bool
            True if the linting process succeeded without errors
        """
        return not len(self.errors)


class DbdFile:
    """
    An expanded EPICS dbd file

    Parameters
    ----------
    fn : str or file
        dbd filename

    Attributes
    ----------
    filename : str
        The dbd filename
    parsed : list
        pyPDB parsed dbd nodes
    """

    def __init__(self, fn):
        if hasattr(fn, "read"):
            self.filename = getattr(fn, "name", None)
            contents = fn.read()
        else:
            self.filename = str(fn)
            with open(fn, "rt") as f:
                contents = f.read()

        self.parsed = _yacc.parse(contents)


def load_database_file(
    dbd: Union[DbdFile, str, pathlib.Path],
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
    dbd : DbdFile or str
        The database definition file; filename or pre-loaded DbdFile
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
    args = []
    if warn_ext_links:
        args.append("-Wext-link")
    if warn_bad_fields:
        args.append("-Wbad-field")
    if warn_rec_append:
        args.append("-Wrec-append")

    if not warn_quoted:
        args.append("-Wno-quoted")
    if not warn_varint:
        args.append("-Wno-varint")
    if not warn_spec_comm:
        args.append("-Wno-spec-comm")

    if full:
        args.append("-F")
    else:
        args.append("-P")

    dbd_file = dbd if isinstance(dbd, DbdFile) else DbdFile(dbd)

    args = _dbdlint.getargs([str(dbd_file.filename), str(db), *args])

    results = LinterResults(args)

    with open(db, "r") as f:
        db_content = f.read()

    if macro_context is not None:
        db_content = '\n'.join(
            macro_context.expand(line)
            for line in db_content.splitlines()
        )

    try:
        _dbdlint.walk(dbd_file.parsed, dbdtree, results)
        parsed_db = _yacc.parse(db_content, file=db)
        _dbdlint.walk(parsed_db, dbdtree, results)
    except DBSyntaxError as ex:
        ex.errors = results.errors
        ex.warnings = results.warnings
        raise

    return results
