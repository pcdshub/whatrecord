import copy
import dataclasses
import os
import pathlib
from dataclasses import field
from typing import ClassVar, Dict, List, Optional, Tuple, Union

import pyPDB.dbd.yacc as _yacc
import pyPDB.dbdlint as _dbdlint
from pyPDB.dbdlint import DBSyntaxError

from .common import LinterError, LinterWarning, RecordField, RecordInstance
from .macro import MacroContext

MAX_RECORD_LENGTH = int(os.environ.get("EPICS_MAX_RECORD_LENGTH", "60"))


def split_record_and_field(pvname) -> Tuple[str, str]:
    """Split REC.FLD into REC and FLD."""
    record, *field = pvname.split(".", 1)
    return record, field[0] if field else ""


def _whole_rec_inst_field(ent, results, info):
    res = _dbdlint.wholeRecInstField(ent, results, info)
    recent, field_name = results.stack[-1], ent.args[0]
    if hasattr(recent, "_fieldinfo"):
        record_type = recent.args[0]
        record_name = recent.args[1]
        ftype = recent._fieldinfo.get(field_name)
        value = ent.args[1]
        results._record_field_defined_by_node(
            node=ent,
            record_type=record_type,
            record_name=record_name,
            field_name=field_name,
            field_type=ftype,
            value=value,
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
dbdtree[_dbdlint.Block]["record"]["tree"][_dbdlint.Block]["field"][
    "wholefn"
] = _whole_rec_inst_field  # noqa: E501
dbdtree[_dbdlint.Block]["record"]["wholefn"] = _whole_rec_inst


@dataclasses.dataclass(repr=False)
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

    warn_options: List[str] = field(default_factory=list)

    # {'ao':{'OUT':'DBF_OUTLINK', ...}, ...}
    rectypes: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # {'ao':{'Soft Channel':'CONSTANT', ...}, ...}
    recdsets: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # {'inst:name':'ao', ...}
    recinst: Dict[str, str] = field(default_factory=dict)

    extinst: List[str] = field(default_factory=list)
    errors: List[LinterError] = field(default_factory=list)
    warnings: List[LinterWarning] = field(default_factory=list)

    # Records with context and field information:
    records: Dict[str, RecordInstance] = field(default_factory=dict)

    # The following are used internally but should not be serialized
    node: ClassVar[object]
    stack: ClassVar[List[object]]

    def __post_init__(self):
        self.node = None
        self.stack = []

    @property
    def _error(self):
        # dbdlint uses this internally; make it more accessible + serialized
        return self.error

    @_error.setter
    def _error(self, error):
        self.error = error

    @property
    def _warning(self):
        # dbdlint uses this internally; make it more accessible + serialized
        return self.warning

    @_warning.setter
    def _warning(self, warning):
        self.warning = warning

    @classmethod
    def from_args(cls, args):
        return cls(
            whole=args.whole,
            # wlvl=logging.ERROR if args.werror else logging.WARN,
            warn_options=list(args.warn),
        )

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"records={len(self.recinst)} "
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

    def _record_field_defined_by_node(
        self, node, record_type, record_name, field_name, field_type, value
    ):
        self.records[record_name].fields[field_name] = RecordField(
            dtype=field_type,
            value=value,
            name=field_name,
            context=(f"{node.fname}:{node.lineno}",),
        )

    def _record_defined_by_node(self, node, name, rtype):
        self.records[name] = RecordInstance(
            context=(f"{node.fname}:{node.lineno}",),
            name=name,
            record_type=rtype,
            fields={},
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

    results = LinterResults.from_args(args)

    with open(db, "r") as f:
        db_content = f.read()

    if macro_context is not None:
        db_content = "\n".join(
            macro_context.expand(line) for line in db_content.splitlines()
        ) + "\n"

    try:
        tree = copy.deepcopy(dbdtree)
        _dbdlint.walk(dbd_file.parsed, tree, results)
        parsed_db = _yacc.parse(db_content, file=db)
        _dbdlint.walk(parsed_db, tree, results)
    except DBSyntaxError as ex:
        ex.errors = results.errors
        ex.warnings = results.warnings
        raise

    return results
