from __future__ import annotations

import logging
import pathlib
import typing
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import (Any, ClassVar, Dict, Generator, List, NamedTuple, Optional,
                    Tuple, Union)

import apischema

if typing.TYPE_CHECKING:
    from .db import LinterResults


logger = logging.getLogger(__name__)


class FrozenContextSingle(NamedTuple):
    file: str
    line: int

    def __repr__(self):
        return f"{self.file}:{self.line}"


# NOTE: (De)serializer methods cannot be used with typing.NamedTuple; in fact,
# apischema uses __set_name__ magic method but it is not called on NamedTuple
# subclass fields.
FrozenLoadContext = Tuple[FrozenContextSingle, ...]
IocInfoDict = Dict[str, Union[str, Dict[str, str], List[str]]]


@dataclass(repr=False)
class LoadContext:
    name: str
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"

    def freeze(self) -> FrozenContextSingle:
        return FrozenContextSingle(self.name, self.line)


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
class IocMetadata:
    name: str = "unset"
    script: pathlib.Path = field(default_factory=pathlib.Path)
    startup_directory: pathlib.Path = field(default_factory=pathlib.Path)
    host: Optional[str] = None
    port: Optional[int] = None
    metadata: Dict[str, Union[str, List[str], Dict[str, str]]] = field(
        default_factory=dict
    )
    macros: Dict[str, str] = field(default_factory=dict)
    standin_directories: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def empty(cls):
        return cls(name="unset", script=pathlib.Path(),
                   startup_directory=pathlib.Path())

    @classmethod
    def from_filename(
        cls,
        filename: Union[pathlib.Path, str],
        *,
        name: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        startup_directory: Optional[pathlib.Path] = None,
        macros: Optional[Dict[str, str]] = None,
        standin_directories: Optional[Dict[str, str]] = None,
        **metadata
    ):
        """Given at minimum a filename, guess the rest."""
        filename = pathlib.Path(filename).expanduser().resolve()
        name = name or filename.parts[-2]  # iocBoot/((ioc-something))/st.cmd
        return cls(
            name=name,
            host=host,
            port=port,
            script=filename,
            startup_directory=startup_directory or filename.parent,
            metadata=metadata,
            macros=macros or {},
            standin_directories=standin_directories or {},
        )

    @classmethod
    def from_dict(cls, iocdict: IocInfoDict, macros: Optional[Dict[str, str]] = None):
        """
        Pick apart a given dictionary, relegating extra info to ``.metadata``.

        Parameters
        ----------
        iocdict : dict
            IOC information dictionary.
        """
        ioc = dict(iocdict)
        name = ioc.pop("name")
        host = ioc.pop("host", None)
        port = ioc.pop("port", None)

        script = ioc.pop("script")
        script = pathlib.Path(str(script)).expanduser().resolve()
        return cls(
            name=name,
            script=script,
            startup_directory=script.parent,
            host=host,
            port=port,
            metadata=ioc,
            macros=macros or {},
        )


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
class RecordInstanceSummary:
    """An abbreviated form of :class:`RecordInstance`."""

    context: FrozenLoadContext
    name: str
    record_type: str
    # fields: Dict[str, RecordField]
    archived: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    # is_grecord: bool = False

    @classmethod
    def from_record_instance(self, instance: RecordInstance) -> RecordInstanceSummary:
        return RecordInstanceSummary(
            context=instance.context,
            name=instance.name,
            record_type=instance.record_type,
            archived=instance.archived,
            metadata=instance.metadata,
            aliases=instance.aliases,
        )


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

    def to_summary(self) -> RecordInstanceSummary:
        """Return a summarized version of the record instance."""
        return RecordInstanceSummary.from_record_instance(self)


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
        apischema.deserializer(
            apischema.conversions.Conversion(
                apischema.conversions.identity, source=cls, target=AsynPortBase
            )
        )

        # Only AsynPortBase serializer must be registered (and updated for each
        # subclass) as a Union, and not be inherited
        AsynPortBase._union = (
            cls if AsynPortBase._union is None else Union[AsynPortBase._union, cls]
        )
        apischema.serializer(
            apischema.conversions.Conversion(
                apischema.conversions.identity,
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
    ioc: Optional[IocMetadata]
    # TODO:
    # - gateway rule matches?


@contextmanager
def time_context():
    """Return a callable to measure the time since context manager init."""
    start_count = perf_counter()

    def inner():
        return perf_counter() - start_count

    yield inner
