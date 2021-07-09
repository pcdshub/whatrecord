from __future__ import annotations

import json
import logging
import pathlib
import typing
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, ClassVar, Dict, Generator, List, Optional, Tuple, Union

import apischema

if typing.TYPE_CHECKING:
    from .db import LinterResults
    from .shell import ShellState

from . import settings, util

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadContext:
    name: str
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"

    @apischema.serializer
    @property
    def as_tuple(self) -> Tuple[str, int]:
        return (self.name, self.line)


@apischema.deserializer
def _load_context_from_tuple(items: Tuple[str, int]) -> LoadContext:
    return LoadContext(*items)


# FullLoadContext = Tuple[LoadContext, ...]
FullLoadContext = List[LoadContext]
IocInfoDict = Dict[str, Union[str, Dict[str, str], List[str]]]


@dataclass(repr=False)
class MutableLoadContext:
    name: str
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"

    def to_load_context(self) -> LoadContext:
        return LoadContext(self.name, self.line)


@dataclass
class IocshCmdArgs:
    """iocshCmd(...) arguments."""
    context: FullLoadContext
    command: str


@dataclass
class IocshRedirect:
    fileno: int
    name: str
    mode: str


@dataclass
class IocshSplit:
    argv: List[str]
    redirects: List[IocshRedirect]
    error: Optional[str]


@dataclass
class IocshResult:
    context: FullLoadContext
    line: str
    outputs: List[str] = field(default_factory=list)
    argv: Optional[List[str]] = None
    error: Optional[str] = None
    redirects: List[IocshRedirect] = field(default_factory=list)
    # TODO: normalize this
    # result: Optional[Union[str, Dict[str, str], IocshCmdArgs, ShortLinterResults]]
    result: Any = None

    @classmethod
    def from_line(cls, line: str, context: Optional[FullLoadContext] = None) -> IocshResult:
        return cls(
            context=context or (),
            line=line,
        )


@dataclass
class IocshScript:
    path: str
    # lines: Tuple[IocshResult, ...]
    lines: List[IocshResult]

    @classmethod
    def from_metadata(cls, md: IocMetadata, sh: ShellState) -> IocshScript:
        if md.looks_like_sh:
            if md.base_version == settings.DEFAULT_BASE_VERSION:
                md.base_version = "unknown"
            return cls.from_general_file(md.script)

        return cls(
            path=str(md.script),
            lines=tuple(
                sh.interpret_shell_script(
                    md.script
                )
            ),
        )

    @classmethod
    def from_interpreted_script(
        cls,
        filename: Union[pathlib.Path, str],
        contents: str,
        sh: ShellState
    ) -> IocshScript:
        return cls(
            path=str(filename),
            lines=tuple(
                sh.interpret_shell_script_text(
                    contents.splitlines(),
                    name=str(filename)
                )
            ),
        )

    @classmethod
    def from_general_file(cls, filename: Union[pathlib.Path, str]):
        # For use when shoehorning in a file that's not _really_ an IOC script
        # TODO: instead rework the api
        with open(filename, "rt") as fp:
            lines = fp.read().splitlines()

        return cls(
            path=str(filename),
            lines=tuple(
                IocshResult.from_line(
                    line, context=(LoadContext(str(filename), lineno), )
                )
                for lineno, line in enumerate(lines, 1)
            ),
        )


@dataclass
class IocshArgument:
    name: str
    type: str


@dataclass
class IocshCommand:
    name: str
    args: List[IocshArgument] = field(default_factory=list)
    usage: Optional[str] = None


@dataclass
class IocshVariable:
    name: str
    value: Optional[str] = None
    type: Optional[str] = None


@dataclass
class GdbBinaryInfo:
    commands: Dict[str, IocshCommand]
    base_version: Optional[str]
    variables: Dict[str, IocshVariable]
    error: Optional[str]


@dataclass
class IocMetadata:
    name: str = "unset"
    script: pathlib.Path = field(default_factory=pathlib.Path)
    startup_directory: pathlib.Path = field(default_factory=pathlib.Path)
    host: Optional[str] = None
    port: Optional[int] = None
    binary: Optional[str] = None
    base_version: str = settings.DEFAULT_BASE_VERSION
    metadata: Dict[str, Any] = field(default_factory=dict)
    macros: Dict[str, str] = field(default_factory=dict)
    standin_directories: Dict[str, str] = field(default_factory=dict)
    commands: Dict[str, IocshCommand] = field(default_factory=dict)
    variables: Dict[str, IocshVariable] = field(default_factory=dict)
    loaded_files: Dict[str, str] = field(default_factory=dict)
    load_success: bool = True

    @property
    def looks_like_sh(self) -> bool:
        """Is the script likely sh/bash/etc?"""
        return self.binary and (
            "bin/sh" in self.binary or
            "bin/bash" in self.binary or
            "env bash" in self.binary or
            "bin/tcsh" in self.binary or
            "/python" in self.binary
        )

    @property
    def _cache_key(self) -> str:
        """Cache key for storing this IOC information in a file."""
        key = "".join(
            str(v)
            for v in (
                self.name,
                str(self.script.resolve()),
                str(self.startup_directory.resolve()),
                str(self.host),
                str(self.port),
            )
        )
        hash = util.get_bytes_sha256(bytes(key, "utf-8"))
        return f"{self.name}.{hash}"

    @property
    def cache_filename(self) -> pathlib.Path:
        metadata_fn = f"{self._cache_key}.IocMetadata.json"
        return pathlib.Path(settings.CACHE_PATH) / metadata_fn

    @property
    def ioc_cache_filename(self) -> pathlib.Path:
        metadata_fn = f"{self._cache_key}.LoadedIoc.json"
        return pathlib.Path(settings.CACHE_PATH) / metadata_fn

    def from_cache(self) -> Optional[IocMetadata]:
        if not settings.CACHE_PATH:
            return

        try:
            with open(self.cache_filename, "rb") as fp:
                return apischema.deserialize(type(self), json.load(fp))
        except FileNotFoundError:
            ...
        except json.decoder.JSONDecodeError:
            # Truncated output file, perhaps
            ...

    def save_to_cache(self) -> bool:
        if not settings.CACHE_PATH:
            return False

        with open(self.cache_filename, "wt") as fp:
            json.dump(apischema.serialize(self), fp=fp)
        return True

    def is_up_to_date(self) -> bool:
        """Is this IOC up-to-date with what is on disk?"""
        if not self.loaded_files:
            return False
        return util.check_files_up_to_date(self.loaded_files)

    async def get_binary_information(self) -> Optional[GdbBinaryInfo]:
        if not self.binary or not pathlib.Path(self.binary).exists():
            return

        try:
            info = await util.run_gdb(
                "gdb_binary_info",
                self.binary,
                cls=GdbBinaryInfo,
            )
        except apischema.ValidationError:
            logger.error(
                "Failed to get gdb information for %s (%s)",
                self.name, self.binary,
                exc_info=True,
            )
            return

        if info.error:
            logger.error(
                "Failed to get gdb information for %s (%s): %s",
                self.name, self.binary, info.error
            )
            return

        self.base_version = info.base_version or self.base_version
        self.commands.update(info.commands)
        self.variables.update(info.variables)
        return info

    @property
    def database_version_spec(self) -> int:
        """Load databases with this specification."""
        # TODO: better version parsing
        try:
            base_major_minor = tuple(
                int(v) for v in self.base_version.split(".")[:2]
            )
            return 3 if base_major_minor < (3, 16) else 4
        except Exception:
            return 3

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
        binary: Optional[str] = None,
        base_version: Optional[str] = settings.DEFAULT_BASE_VERSION,
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
            binary=binary or util.find_binary_from_hashbang(filename),
            base_version=base_version,
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
        binary = ioc.pop("binary", None)
        base_version = ioc.pop("base_version", None)
        return cls(
            name=name,
            script=script,
            startup_directory=script.parent,
            host=host,
            port=port,
            metadata=ioc,
            macros=macros or {},
            binary=binary or util.find_binary_from_hashbang(script),
            base_version=base_version or settings.DEFAULT_BASE_VERSION,
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


PVAJsonField = Dict[str, str]


@dataclass
class RecordField:
    dtype: str
    name: str
    value: Any
    context: FullLoadContext

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """field({{name}}, "{{value}}")""",
        "console-verbose": """\
field({{name}}, "{{value}}")  # {{dtype}}{% if context %}; {{context[-1]}}{% endif %}\
""",
    }

    def update_unknowns(self, other: RecordField, *, unknown_values=None,
                        dbd=None):
        """
        If this RecordField has some missing information ("unknown"), fill
        it in with information from the other field.
        """
        unknown_values = unknown_values or {"unknown", "", "(unknown-record)"}
        if other.dtype not in unknown_values and self.dtype in unknown_values:
            self.dtype = other.dtype
        if other.value not in unknown_values and self.value in unknown_values:
            self.value = other.value
        if len(other.context) and len(self.context) == 1:
            ctx, = self.context
            if ctx.name in unknown_values:
                # Even if the other context is unknown, let's take it anyway:
                self.context = other.context
        # if dbd is not None:


PVRelations = Dict[
    str, Dict[str, List[Tuple[RecordField, RecordField, List[str]]]]
]


ScriptPVRelations = Dict[
    str, Dict[str, List[str]]
]


def get_link_information(link_str: str) -> Tuple[str, Tuple[str, ...]]:
    """Get link information from a DBF_{IN,OUT,FWD}LINK value."""
    if isinstance(link_str, dict):
        # Oh, PVA...
        raise ValueError("PVA links are TODO, sorry")

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

    link_details = tuple(additional_info.split(" ")) if additional_info else ()
    return link_str, link_details


LINK_TYPES = {"DBF_INLINK", "DBF_OUTLINK", "DBF_FWDLINK"}


@dataclass
class RecordInstanceSummary:
    """An abbreviated form of :class:`RecordInstance`."""

    context: FullLoadContext
    name: str
    record_type: str
    # fields: Dict[str, RecordField]
    archived: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    # is_grecord: bool = False
    is_pva: bool = False
    owner: str = ""

    @classmethod
    def from_record_instance(self, instance: RecordInstance) -> RecordInstanceSummary:
        return RecordInstanceSummary(
            context=instance.context,
            name=instance.name,
            record_type=instance.record_type,
            archived=instance.archived,
            metadata=instance.metadata,
            aliases=instance.aliases,
            is_pva=instance.is_pva,
            owner=instance.owner,
        )


class StringWithContext(str):
    """A string with LoadContext."""
    __slots__ = ("context", )
    context: Optional[FullLoadContext]

    def __new__(cls, value, context: Optional[FullLoadContext] = None):
        self = super().__new__(cls, value)
        self.context = context
        return self


@dataclass
class PVAFieldReference:
    context: FullLoadContext
    name: str = ""
    record_name: str = ""
    field_name: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """\
PVAFieldReference: {{ record_name }}.{{ field_name }}
                 - {{ metadata }}
""",
    }


AnyField = Union[RecordField, PVAFieldReference]


@dataclass
class RecordInstance:
    context: FullLoadContext
    name: str
    record_type: str
    fields: Dict[str, AnyField] = field(default_factory=dict)
    archived: bool = False
    metadata: Dict[StringWithContext, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    is_grecord: bool = False
    is_pva: bool = False

    # For the convenience of downstream clients, redundantly keep track of the
    # associated IOC:
    owner: str = ""

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """\
record("{{record_type}}", "{{name}}") {
{% if owner %}
    # Part of {{ owner }}
{% endif %}
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
    name: str
    owner: Optional[str]
    instances: List[RecordInstance]
    asyn_ports: List[AsynPortBase]
    ioc: Optional[IocMetadata]
    # TODO:
    # - gateway rule matches?

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """\
{{ name }}:
    Owner: {{ present }}
{% set ioc_info = render_object(ioc, "console") %}
    IOC: {{ ioc_info }}
{% for instance in instances %}
{% set instance_info = render_object(instance, "console") %}
    {{ instance_info | indent(4)}}
{% endfor %}
{% for asyn_port in asyn_ports %}
{% set asyn_info = render_object(asyn_port, "console") %}
    {{ asyn_info | indent(4)}}
{% endfor %}
}
""",
    }


@contextmanager
def time_context():
    """Return a callable to measure the time since context manager init."""
    start_count = perf_counter()

    def inner():
        return perf_counter() - start_count

    yield inner
