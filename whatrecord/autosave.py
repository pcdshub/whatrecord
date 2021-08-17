from __future__ import annotations

import re
from dataclasses import field
from typing import Dict, List, Optional, Union

import lark

from . import transformer
from .common import FullLoadContext, dataclass
from .transformer import context_from_token


@dataclass
class RestoreError:
    context: FullLoadContext
    number: int
    description: str


@dataclass
class RestoreValue:
    context: FullLoadContext
    pvname: str
    record: str
    field: str
    value: Union[str, List[str]]


@dataclass
class AutosaveRestoreFile:
    """Representation of an autosave restore (.sav) file."""
    filename: str
    values: Dict[str, Dict[str, RestoreValue]] = field(default_factory=dict)
    disconnected: List[str] = field(default_factory=list)
    errors: List[RestoreError] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)

    @classmethod
    def from_string(
        cls, contents, filename=None,
    ) -> AutosaveRestoreFile:
        """Load an autosave file given its string contents."""
        grammar = lark.Lark.open_from_package(
            "whatrecord",
            "autosave_save.lark",
            search_paths=("grammar", ),
            parser="earley",
            propagate_positions=True,
        )

        return _AutosaveRestoreTransformer(cls, filename).transform(
            grammar.parse(contents)
        )

    @classmethod
    def from_file_obj(cls, fp, filename=None) -> AutosaveRestoreFile:
        """Load an autosave file given a file object."""
        return cls.from_string(
            fp.read(),
            filename=getattr(fp, "name", filename),
        )

    @classmethod
    def from_file(cls, fn) -> AutosaveRestoreFile:
        """
        Load an autosave restore (.sav) file.

        Parameters
        ----------
        filename : pathlib.Path or str
            The filename.

        Returns
        -------
        file : AutosaveRestoreFile
            The resulting parsed file.
        """
        with open(fn, "rt") as fp:
            return cls.from_string(fp.read(), filename=fn)


@lark.visitors.v_args(inline=True)
class _AutosaveRestoreTransformer(lark.visitors.Transformer):
    def __init__(self, cls, fn, visit_tokens=False):
        super().__init__(visit_tokens=visit_tokens)
        self.fn = str(fn)
        self.cls = cls
        self.errors = []
        self.restores = {}
        self.comments = []
        self.disconnected = []

    @lark.visitors.v_args(tree=True)
    def restore(self, body):
        return self.cls(
            filename=self.fn,
            values=self.restores,
            errors=self.errors,
            comments=self.comments,
            disconnected=self.disconnected,
        )

    restore_item = transformer.pass_through

    def error(self, exclamation, error_number, error_description=None):
        self.errors.append(
            RestoreError(
                context=transformer.context_from_token(self.fn, exclamation),
                number=error_number,
                description=str(error_description or ""),
            )
        )

    def value_restore(self, pvname, value=None):
        context = context_from_token(self.fn, pvname)
        if "." in pvname:
            record, field = pvname.split(".", 1)
        else:
            record, field = pvname, "VAL"

        record = str(record)
        if record not in self.restores:
            self.restores[record] = {}

        self.restores[record][field.lstrip(".")] = RestoreValue(
            context=context,
            record=record,
            pvname=f"{record}.{field}" if field else record,
            field=str(field),
            value=value if isinstance(value, list) else _fix_value(value),
        )

    value = transformer.pass_through
    record_name = transformer.pass_through
    scalar_value = transformer.pass_through
    pvname = transformer.pass_through

    def array_elements(self, *elements):
        return [_fix_value(elem) for elem in elements]

    def array_value(self, array_marker, array_begin, elements, array_end):
        return list(elements)

    def error_number(self, number):
        return int(number)

    error_description = transformer.stringify

    def comment(self, comment):
        comment = comment.lstrip("# ")
        if not comment:
            return

        parts = comment.split(" ")
        if len(parts) == 3 and parts[-2:] == ["Search", "Issued"]:
            self.disconnected.append(parts[0])
        else:
            self.comments.append(comment)


def _strip_double_quote(value: str) -> str:
    """Strip one leading/single trailing double-quote."""
    if value[0] == '"':
        value = value[1:]
    if value[-1] == '"':
        value = value[:-1]
    return value


RE_REMOVE_ESCAPE = re.compile(r"\\(.)")


def _fix_value(value: Optional[str]) -> str:
    """Remove quotes, and fix up escaping."""
    if value is None:
        # Value can be empty in autosave files
        return ""
    value = _strip_double_quote(value)
    return RE_REMOVE_ESCAPE.sub(r"\1", value)
