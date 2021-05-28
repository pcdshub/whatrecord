from __future__ import annotations

import logging
import typing
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, ClassVar, Dict, Generator, List, Optional, Tuple, Union

from apischema import deserializer, serializer
from apischema.conversions import Conversion, identity

if typing.TYPE_CHECKING:
    from .db import LinterResults


logger = logging.getLogger(__name__)


# FrozenLoadContext = List[Tuple[str, int], ...]
FrozenLoadContext = List[List[Union[str, int]]]


@dataclass(repr=False)
class LoadContext:
    name: str
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"

    def freeze(self) -> Tuple[str, int]:
        return (self.name, self.line)


@dataclass
class IocshCommand:
    context: FrozenLoadContext
    command: str


@dataclass
class IocshResult:
    context: FrozenLoadContext
    line: str
    outputs: List[str]
    argv: Optional[List[str]]
    error: Optional[str]
    redirects: Dict[str, Dict[str, str]]
    # TODO: normalize this
    result: Optional[Union[str, Dict[str, str], IocshCommand, ShortLinterResults]]


@dataclass
class IocshScript:
    path: str
    lines: Tuple[IocshResult, ...]


@dataclass
class LinterMessage:
    name: str
    file: str
    line: int
    message: str


@dataclass
class LinterWarning(LinterMessage):
    ...


@dataclass
class LinterError(LinterMessage):
    ...


@dataclass
class ShortLinterResults:
    load_count: int
    errors: List[LinterError]
    warnings: List[LinterWarning]
    macros: Dict[str, str]

    @classmethod
    def from_full_results(cls, results: LinterResults, macros: Dict[str, str]):
        return cls(
            load_count=len(results.records),
            errors=results.errors,
            warnings=results.warnings,
            macros=macros,
        )


@dataclass
class RecordField:
    dtype: str
    name: str
    value: str
    context: FrozenLoadContext

    _jinja_format_: ClassVar[dict] = {
        "console": """field({{name}}, "{{value}}")""",
        "console-verbose": """\
field({{name}}, "{{value}}")  # {{dtype}}{% if context %}; {{context[-1]}}{% endif %}\
""",
    }


def get_link_information(link_str: str) -> Tuple[str, Tuple[str, ...]]:
    """Get link information from a DBF_{IN,OUT,FWD}LINK value."""
    if " " in link_str:
        # strip off PP/MS/etc (TODO might be useful later)
        link_str, additional_info = link_str.split(" ", 1)
    else:
        additional_info = ""

    if link_str.startswith("@"):
        # TODO asyn/device links
        raise ValueError("asyn link")
    if not link_str:
        raise ValueError("empty link")

    if link_str.isnumeric():
        # 0 or 1 usually and not a string
        raise ValueError("integral link")

    try:
        float(link_str)
    except Exception:
        # Good, we don't want a float
        ...
    else:
        raise ValueError("float link")

    return link_str, tuple(additional_info.split(" "))


LINK_TYPES = {"DBF_INLINK", "DBF_OUTLINK", "DBF_FWDLINK"}


@dataclass
class RecordInstance:
    context: FrozenLoadContext
    name: str
    record_type: str
    fields: Dict[str, RecordField]
    archived: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    is_grecord: bool = False

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

    def get_fields_of_type(self, *types) -> Generator[RecordField, None, None]:
        """Get all fields of the matching type(s)."""
        for fld in self.fields.values():
            if fld.dtype in types:
                yield fld

    def get_links(
        self,
    ) -> Generator[Tuple[RecordField, str, Tuple[str, ...]], None, None]:
        """Get all links."""
        for fld in self.get_fields_of_type(*LINK_TYPES):
            try:
                link, info = get_link_information(fld.value)
            except ValueError:
                continue
            yield fld, link, info


class AsynPortBase:
    """
    Base class for general asyn ports.

    Used in :mod:`whatrecord.asyn`, but made available here such that apischema
    can find it more readily.
    """
    _union: Any = None

    def __init_subclass__(cls, **kwargs):
        # Registers new subclasses automatically in the union cls._union.

        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=AsynPortBase))

        # Only AsynPortBase serializer must be registered (and updated for each
        # subclass) as a Union, and not be inherited
        AsynPortBase._union = (
            cls if AsynPortBase._union is None else Union[AsynPortBase._union, cls]
        )
        serializer(
            Conversion(
                identity,
                source=AsynPortBase,
                target=AsynPortBase._union,
                inherited=False,
            )
        )


@dataclass
class WhatRecord:
    owner: Optional[str]
    instance: RecordInstance
    asyn_ports: List["AsynPortBase"]
    # TODO:
    # - IOC host info, port?
    # - gateway rule matches?


@contextmanager
def time_context():
    """Return a callable to measure the time since context manager init."""
    start_count = perf_counter()

    def inner():
        return perf_counter() - start_count

    yield inner
