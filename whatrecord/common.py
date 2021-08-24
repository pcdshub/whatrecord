from __future__ import annotations

import enum
import functools
import inspect
import json
import logging
import pathlib
import textwrap
import typing
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import (Any, Callable, ClassVar, Dict, Generator, List, Optional,
                    Tuple, Union)

import apischema
import lark

from _whatrecord.common import IocshRedirect

if typing.TYPE_CHECKING:
    from .shell import ShellState

from . import settings, util

logger = logging.getLogger(__name__)


class FileFormat(str, enum.Enum):
    iocsh = 'iocsh'
    database = 'database'
    database_definition = 'database_definition'
    substitution = 'substitution'
    gateway_pvlist = 'gateway_pvlist'
    access_security = 'access_security'
    stream_protocol = 'stream_protocol'

    @classmethod
    def from_extension(cls, extension: str) -> FileFormat:
        """Get a file format based on a file extension."""
        return {
            "cmd": FileFormat.iocsh,
            "db": FileFormat.database,
            "dbd": FileFormat.database_definition,
            "template": FileFormat.database,
            "substitutions": FileFormat.substitution,
            "pvlist": FileFormat.gateway_pvlist,
            "acf": FileFormat.access_security,
            "proto": FileFormat.stream_protocol,
        }[extension.lower()]

    @classmethod
    def from_filename(cls, filename: AnyPath) -> FileFormat:
        """Get a file format based on a full filename."""
        extension = pathlib.Path(filename).suffix.lstrip(".")
        try:
            return FileFormat.from_extension(extension)
        except KeyError:
            raise ValueError(
                f"Could not determine file type from extension: {extension}"
            ) from None


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
AnyPath = Union[str, pathlib.Path]


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


@apischema.fields.with_fields_set
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

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """
{%- for ctx in context -%}
    {{ctx.line}}:
{%- endfor %} {{ line }}
{% if error %}
    ** ERROR on line {% if context %}{{ context[0].line }}{% endif %} **
    {{ error | indent(4) }}
{% endif %}
{% if outputs != [line] %}
{% for output in outputs %}
    -SH> {{ output | indent(6) }}
{% endfor %}
{% endif %}
{% for redirect in redirects %}
    -> Redirect: {{ redirect }}
{%- endfor %}
""".strip(),
    }


@dataclass
class IocshScript:
    path: str
    # lines: Tuple[IocshResult, ...]
    lines: List[IocshResult]

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": textwrap.dedent(
            """\
            {%- for line in lines %}
            {% set line = render_object(line, "console") %}
            {{ line }}
            {%- endfor %}
            """.rstrip(),
        ),
        "console-verbose": textwrap.dedent(
            """\
            {%- for line in lines -%}
            {% set line = render_object(line, "console-verbose") %}
            {{ line }}
            {%- endfor %}
            """.rstrip(),
        )
    }

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
                IocshResult(
                    line=line,
                    context=(LoadContext(str(filename), lineno), )
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
    context: Optional[FullLoadContext] = None


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

    def update(self, other: IocMetadata, merge: bool = False):
        """
        Update the metadata with a new set from an IOC Loader.

        Parameters
        ----------
        other : IocMetadata
            The other IOC metadata to update this instance with.

        merge : bool, optional
            Merge in dictionary information, or overwrite it.  Defaults to
            'overwrite' (merge=False).
        """
        self.name = other.name
        self.script = other.script
        self.startup_directory = other.startup_directory
        self.host = other.host or self.host
        self.port = other.port or self.port
        self.binary = other.binary or self.binary
        self.base_version = (
            other.base_version
            if other.base_version != settings.DEFAULT_BASE_VERSION
            else self.base_version
        )

        if merge:
            self.metadata.update(other.metadata)
            self.macros.update(other.macros)
            self.standin_directories.update(other.standin_directories)
            self.commands.update(other.commands)
            self.variables.update(other.variables)
        else:
            self.metadata = dict(other.metadata)
            self.macros = dict(other.macros)
            self.standin_directories = dict(other.standin_directories)
            self.commands = dict(other.commands)
            self.variables = dict(other.variables)

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

    def add_loaded_file(
        self,
        filename: Union[pathlib.Path, str],
        update: bool = False,
    ) -> bool:
        """
        Add filename to the loaded file dictionary, optionally updating an
        existing hash.
        """
        filename = pathlib.Path(self.startup_directory) / filename
        if str(filename) not in self.loaded_files or update:
            self.loaded_files[str(filename)] = util.get_file_sha256(filename)
            return True
        return False

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

        for command in self.commands.values():
            for context in command.context or []:
                try:
                    self.add_loaded_file(context.name)
                except FileNotFoundError:
                    logger.debug(
                        "GDB source file does not exist for command %s (%s)",
                        command.name, context
                    )
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
        if "/" in name:
            name = name.replace("/", "")
            if not name:
                # Sorry, we need something unique here (better ideas welcome)
                name = util.get_bytes_sha256(bytes(str(filename), "utf-8"))[:10]

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
    line: int
    message: str


@dataclass
class LinterWarning(LinterMessage):
    ...


@dataclass
class LinterError(LinterMessage):
    ...


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
    info: Dict[str, str] = field(default_factory=dict)
    # metadata: Dict[str, Any] = field(default_factory=dict)
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
            info=instance.info,
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
class DatabaseMenu:
    context: FullLoadContext
    name: str
    choices: Dict[str, str]


@dataclass
class DatabaseDevice:
    record_type: str
    link_type: str
    dset_name: str
    choice_string: str


@apischema.fields.with_fields_set
@dataclass
class RecordTypeField:
    context: FullLoadContext
    name: str
    type: str
    asl: Optional[str] = None
    initial: Optional[str] = None
    promptgroup: Optional[str] = None
    prompt: Optional[str] = None
    special: Optional[str] = None
    pp: Optional[str] = None
    interest: Optional[str] = None
    base: Optional[str] = None
    size: Optional[str] = None
    extra: Optional[str] = None
    menu: Optional[str] = None
    prop: Optional[str] = None
    # -> bundle the remainder in "body", even if unrecognized
    body: Dict[str, str] = field(default_factory=dict)


@dataclass
class RecordType:
    context: FullLoadContext
    name: str
    cdefs: List[str] = field(default_factory=list)
    fields: Dict[str, RecordTypeField] = field(default_factory=dict)
    devices: Dict[str, DatabaseDevice] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    info: Dict[str, str] = field(default_factory=dict)
    is_grecord: bool = False


@dataclass
class RecordInstance:
    context: FullLoadContext
    name: str
    record_type: str
    fields: Dict[str, AnyField] = field(default_factory=dict)
    info: Dict[StringWithContext, Any] = field(default_factory=dict)
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
    {{ field_text | indent(4) }}
{% endfor %}
}
""",
    }

    @property
    def access_security_group(self) -> str:
        """The access security group name for the record."""
        if "ASG" in self.fields and not self.is_pva:
            return str(self.fields["ASG"].value)
        return "DEFAULT"

    def get_fields_of_type(self, *types) -> Generator[RecordField, None, None]:
        """Get all fields of the matching type(s)."""
        if self.is_pva:
            return

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
class ShellStateHandler:
    metadata_key: ClassVar[str]
    parent: Optional[ShellStateHandler] = field(
        default=None, metadata=apischema.metadata.skip,
        repr=False, hash=False, compare=False
    )
    primary_handler: Optional[ShellState] = field(
        default=None, metadata=apischema.metadata.skip,
        repr=False, hash=False, compare=False
    )
    _handlers: Dict[str, Callable] = field(
        default_factory=dict, metadata=apischema.metadata.skip,
        repr=False, hash=False, compare=False, init=False
    )

    def __post_init__(self):
        self._handlers.update(dict(self.find_handlers()))
        self._init_sub_handlers_()

    def _init_sub_handlers_(self):
        """Initialize sub-handlers with parent/primary_handler."""
        for sub_handler in self.sub_handlers:
            sub_handler.parent = self
            sub_handler.primary_handler = getattr(self.parent, "primary_handler", self)
            sub_handler._init_sub_handlers_()

    def annotate_record(self, instance: RecordInstance) -> Optional[Dict[str, Any]]:
        """Annotate the given record's metadata with state-related information."""
        ...

    def get_load_context(self) -> FullLoadContext:
        """Get a FullLoadContext tuple representing where we are now."""
        if self.primary_handler is None:
            return tuple()
        return self.primary_handler.get_load_context()

    @property
    def sub_handlers(self) -> List[ShellStateHandler]:
        """Handlers which contain their own state."""
        return []

    @staticmethod
    def generic_handler_decorator(func=None, stub=False):
        """
        Decorate a handler method to generically return parameter-to-value
        information.

        This can be in addition to or in place of GDB command information.

        Parameters
        ----------
        func : callable
            The ``handler_`` method.

        stub : bool, optional
            Mark this as a stub method.  Variable arguments will be filled in
            as necessary, even if defaults are not provided.
        """

        def wrap(func):
            params = list(inspect.signature(func).parameters.items())[1:]
            defaults = list(
                None if param.default is inspect.Parameter.empty
                else param.default
                for _, param in params
            )

            @functools.wraps(func)
            def wrapped(self, *args):
                result = {}
                if len(args) < len(params) and stub:
                    # Pad unspecified arguments with defaults or "None"
                    args = list(args) + defaults[len(args):]

                if len(args) > len(params):
                    result["argument_lint"] = "Too many arguments"

                result["arguments"] = [
                    {
                        "name": name,
                        "type": getattr(param.annotation, "__name__", param.annotation),
                        "value": value,
                    }
                    for (name, param), value in zip(params, args)
                ]

                call_result = func(self, *args[:len(params)])
                if call_result is not None:
                    for key, value in call_result.items():
                        if key in result:
                            result[key].update(value)
                        else:
                            result[key] = value

                return result
            return wrapped

        if func is not None:
            return wrap(func)

        return wrap

    def find_handlers(self) -> Generator[Tuple[str, Callable], None, None]:
        """Find all IOC shell command handlers by name."""
        for handler_obj in [self] + self.sub_handlers:
            for attr in dir(handler_obj):
                if attr.startswith("handle_"):
                    obj = getattr(handler_obj, attr, None)
                    if callable(obj):
                        name = attr.split("_", 1)[1]
                        yield name, obj

            if handler_obj is not self:
                yield from handler_obj.find_handlers()

    def pre_ioc_init(self):
        """Pre-iocInit hook."""
        ...

    def post_ioc_init(self):
        """Post-iocInit hook."""
        ...


@dataclass
class RecordDefinitionAndInstance:
    """A pair of V3 record definition and instance."""
    definition: Optional[RecordType]
    instance: RecordInstance

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """\
{% set instance_info = render_object(instance, "console") %}
{{ instance_info }}
""",
    }


@dataclass
class WhatRecord:
    """
    WhatRecord - full set of information regarding a specific record.

    This response is on a per-IOC basis, so at most it can return one V3 record
    and one V4 record, as these exist in separate namespaces.


    Attributes
    ----------
    name : str
        The record name.

    record : RecordDefinitionAndInstance, optional
        The V3 record definition (if available) and record instance.

    pva_group : RecordInstance, optional
        The PVAccess group, if available.

    ioc : IocMetadata, optional
        The associated IOC metadata, if available.
    """
    name: str
    record: Optional[RecordDefinitionAndInstance] = None
    menus: Optional[Dict[str, DatabaseMenu]] = None
    pva_group: Optional[RecordInstance] = None
    ioc: Optional[IocMetadata] = None

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """\
{{ name }}:
    Owner: {{ present }}
{% set ioc_info = render_object(ioc, "console") %}
    IOC: {{ ioc_info }}
{% if record %}
{% set instance_info = render_object(record, "console") %}
    {{ instance_info | indent(4)}}
{% endif %}
{% if pva_group %}
{% set instance_info = render_object(pva_group, "console") %}
    {{ instance_info | indent(4)}}
{% endif %}
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


def context_from_lark_token(fn: str, token: lark.Token) -> FullLoadContext:
    """Get a full load context from a given lark Token."""
    return (LoadContext(name=fn, line=token.line), )


def remove_redundant_context(full_context: FullLoadContext) -> FullLoadContext:
    """Remove redundant context information if it does not add anything."""
    if not full_context:
        return full_context

    # Inefficient, but the data set is small here, so meh
    zero_line_files = set(
        item.name
        for item in full_context
        if item.line == 0
    )

    for file in set(zero_line_files):
        for ctx in full_context:
            if ctx.name == file and ctx.line > 0:
                break
        else:
            zero_line_files.remove(file)

    return tuple(
        ctx
        for ctx in full_context
        if ctx.name not in zero_line_files or ctx.line > 0
    )
