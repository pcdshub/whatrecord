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
                    Sequence, Tuple, Union)

import apischema
import epicsmacrolib
import lark

if typing.TYPE_CHECKING:
    from .shell import ShellState

from . import settings, util

logger = logging.getLogger(__name__)


class FileFormat(str, enum.Enum):
    """
    File type enum that covers all formats supported by whatrecord.
    """
    iocsh = 'iocsh'
    database = 'database'
    database_definition = 'database_definition'
    substitution = 'substitution'
    gateway_pvlist = 'gateway_pvlist'
    access_security = 'access_security'
    stream_protocol = 'stream_protocol'
    state_notation = 'state_notation'
    makefile = 'makefile'

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
            "st": FileFormat.state_notation,
        }[extension.lower()]

    @classmethod
    def from_filename(cls, filename: AnyPath) -> FileFormat:
        """Get a file format based on a full filename."""
        path = pathlib.Path(filename)
        extension = path.suffix.lstrip(".")
        if not extension and path.name.startswith("Makefile"):
            return FileFormat.makefile

        try:
            return FileFormat.from_extension(extension)
        except KeyError:
            raise ValueError(
                f"Could not determine file type from extension: {extension}"
            ) from None


@dataclass(frozen=True)
class LoadContext:
    """File and line context information."""
    #: The filename (or other identifier) to identify the context.
    name: str
    #: The line number of ``name`` this applies to.
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"

    @apischema.serializer
    @property
    def as_tuple(self) -> Sequence[Union[str, int]]:
        return [self.name, self.line]


@apischema.deserializer
def _load_context_from_tuple(items: Sequence[Union[str, int]]) -> LoadContext:
    """
    A deserializer that takes in e.g., ["file", line] and turns it into a LoadContext.
    """
    return LoadContext(*items)


# FullLoadContext = Tuple[LoadContext, ...]
FullLoadContext = Sequence[LoadContext]
IocInfoDict = Dict[str, Union[str, Dict[str, str], List[str]]]
AnyPath = Union[str, pathlib.Path]


@dataclass(repr=False)
class MutableLoadContext:
    """
    A mutable (i.e., changeable) version of :class:`LoadContext`.
    """
    name: str
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"

    def to_load_context(self) -> LoadContext:
        """Convert this to an immutable LoadContext."""
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
    redirects: List[epicsmacrolib.IocshRedirect] = field(default_factory=list)
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
    {{ error | indent(_fmt.indent) }}
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
    """An IOC Shell script (i.e., st.cmd) that was loaded and interpreted."""
    #: The path to the script.
    path: str
    #: Interpreted lines of the script.
    lines: List[IocshResult]

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "file": textwrap.dedent(
            """\
            {%- for line in lines %}
            {% if line.context | length == 1 %}
            {{ line.line }}
            {% endif %}
            {%- endfor -%}
            """.rstrip(),
        ),
        "console": textwrap.dedent(
            """\
            {%- for line in lines %}
            {{ render_object(line, "console") }}
            {%- endfor %}
            """.rstrip(),
        ),
        "console-verbose": textwrap.dedent(
            """\
            {%- for line in lines -%}
            {{ render_object(line, "console-verbose") }}
            {%- endfor %}
            """.rstrip(),
        )
    }

    @classmethod
    def from_metadata(cls, md: IocMetadata, sh: ShellState) -> IocshScript:
        """
        Create an IocshScript provided IocMetadata and ShellState.

        Parameters
        ----------
        md : IocMetadata
            Metadata identifying the IOC.
        sh : ShellState
            The state of the shell interpreter after interpreting the IOC
            startup script.

        Returns
        -------
        IocshScript
        """
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
        """
        Create an IocshScript provided a filename, its contents, and ShellState.

        Parameters
        ----------
        filename : str
            The script filename.
        contents : str
            The decoded string contents of the file.
        sh : ShellState
            The state of the shell interpreter after interpreting the IOC
            startup script.

        Returns
        -------
        IocshScript
        """
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
    def from_general_file(cls, filename: Union[pathlib.Path, str]) -> IocshScript:
        """
        Create an IocshScript from any given file, even non-startup scripts.

        This can be used to transfer database files over to the frontend, for
        example.

        Parameters
        ----------
        filename : Union[pathlib.Path, str]
            The filename.

        Returns
        -------
        """
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
    """A single argument in a shell command."""
    #: The name of the argument.
    name: str
    #: Its type, according to EPICS.
    type: str


@dataclass
class IocshCommand:
    """
    A registered shell command.

    Largely used as part of the gdb binary information tool.
    """
    #: The name of the command.
    name: str
    #: Arguments the user can pass to the command.
    args: List[IocshArgument] = field(default_factory=list)
    #: Usage information.
    usage: Optional[str] = None
    #: Where this command information came from.
    context: Optional[FullLoadContext] = None


@dataclass
class IocshVariable:
    """
    A registered shell variable.

    Largely used as part of the gdb binary information tool.
    """
    #: The name of the variable.
    name: str
    #: The last value of the variable.
    value: Optional[str] = None
    #: The type of the variable, according to EPICS.
    type: Optional[str] = None


@dataclass
class GdbBinaryInfo:
    """
    GDB-derived binary information.

    This is populated by deserializing the output of
    ``whatrecord.plugins.gdb_binary_info``, which is interpreted by GDB itself.
    """
    #: Commands that are available to the user in an EPICS IOC shell.
    commands: Dict[str, IocshCommand]
    #: The base version detected in the binary.
    base_version: Optional[str]
    #: Variables available to be set in the shell.
    variables: Dict[str, IocshVariable]
    #: GDB plugin error information.
    error: Optional[str]


def get_grammar_version_by_base_version(base_version: str) -> int:
    """
    Database grammar version to use, provided the epics-base version.

    Returns
    -------
    base_version : str
        The epics-base version number.

    Returns
    -------
    int
        If R3.15 or under, ``3``, otherwise ``4``.
    """
    base_version = base_version.lstrip("vRr")
    major_minor = tuple(
        int(v) for v in base_version.split(".")[:2]
    )
    return 3 if major_minor < (3, 16) else 4


@dataclass
class IocMetadata:
    """
    Metadata identifying an IOC.
    """
    #: The name of the IOC.
    name: str = "unset"
    #: The IOC startup script.
    script: pathlib.Path = field(default_factory=pathlib.Path)
    #: The startup directory to use when interpreting the script.
    startup_directory: pathlib.Path = field(default_factory=pathlib.Path)
    #: The host that the IOC will be run on, if available.
    host: Optional[str] = None
    #: The port on the host that the IOC will be available on, if available.
    port: Optional[int] = None
    #: The path to the IOC binary.
    binary: Optional[str] = None
    #: The EPICS-base version.
    base_version: str = settings.DEFAULT_BASE_VERSION
    #: User-specified metadata about the IOC.
    metadata: Dict[str, Any] = field(default_factory=dict)
    #: Macros to include when loading the IOC.
    macros: Dict[str, str] = field(default_factory=dict)
    #: Stand-in directories to use when interpreting a script outside of its
    #: normal environment.
    standin_directories: Dict[str, str] = field(default_factory=dict)
    #: Commands available to be used in the IOC shell.
    commands: Dict[str, IocshCommand] = field(default_factory=dict)
    #: Variables that are defined for usage in the shell.
    variables: Dict[str, IocshVariable] = field(default_factory=dict)
    #: Files that were loaded with their hash as a value.
    loaded_files: Dict[str, str] = field(default_factory=dict)
    #: Whether the IOC was successfully loaded or not.
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
        """The cache filename for this metadata."""
        metadata_fn = f"{self._cache_key}.IocMetadata.json"
        return pathlib.Path(settings.CACHE_PATH) / metadata_fn

    @property
    def ioc_cache_filename(self) -> pathlib.Path:
        """The cache filename for the entire interpreted IOC."""
        metadata_fn = f"{self._cache_key}.LoadedIoc.json"
        return pathlib.Path(settings.CACHE_PATH) / metadata_fn

    def from_cache(self) -> Optional[IocMetadata]:
        """Load metadata from the cache, if available."""
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
        """Save this metadata to the cache, if enabled."""
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

        Parameters
        ----------
        filename : Union[pathlib.Path, str]
            The filename.
        update : bool, optional
            Update a hash if the filename is already in the loaded_files
            dictionary.

        Returns
        -------
        bool
            Set if a hash was updated in the loaded_files dictionary.
        """
        filename = pathlib.Path(self.startup_directory) / filename
        if str(filename) not in self.loaded_files or update:
            self.loaded_files[str(filename)] = util.get_file_sha256(filename)
            return True
        return False

    async def get_binary_information(self) -> Optional[GdbBinaryInfo]:
        """
        Get binary information using the GDB plugin.

        Requires that gdb be available, along with the ``.binary`` be set
        to a valid file.
        """
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
        """
        Load databases with this specification.

        Returns
        -------
        version_spec : int
            If R3.15 or under, ``3``, otherwise ``4``.
        """
        # TODO: better version parsing

        for base_version in [self.base_version, settings.DEFAULT_BASE_VERSION]:
            try:
                return get_grammar_version_by_base_version(base_version)
            except Exception:
                ...

        return 3

    @classmethod
    def from_file(
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
    ) -> IocMetadata:
        """
        Given at minimum a filename, guess the rest of the metadata.

        Parameters
        ----------
        filename : pathlib.Path or str
            The IOC startup script filename.
        name : str, optional
            The name of the IOC.  Defaults to the startup script's parent
            directory name.
        host : str, optional
            The host on which the IOC runs.
        port : int, optional
            The port on which the IOC will be accessible from the host.
        startup_directory : pathlib.Path, optional
            The directory in which the script should be started.  Defaults
            to the parent directory of ``filename``.
        macros : Dict[str, str], optional
            Macros to use when interpreting the startup script.
        standin_directories : Dict[str, str], optional
            Stand-in directories to use when interpreting a script outside of
            its normal environment.
        binary : str, optional
            The binary used to run the startup script normally. That is, an
            EPICS IOC binary.  If not specified, this will be determined
            based on the startup script hashbang (if available).
        base_version : str, optional
            The epics-base version to use when interpreting the startup script.
            This may be overridden automatically when interpreting the startup
            script.
        **metadata :
            User-specified metadata.

        Returns
        -------
        IocMetadata
        """
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

    #: Back-compat: from_filename is deprecated
    from_filename = from_file

    @classmethod
    def from_dict(
        cls, iocdict: IocInfoDict, macros: Optional[Dict[str, str]] = None
    ) -> IocMetadata:
        """
        Create an IocMetadata instance.

        Pick apart a given ``iocdict`` dictionary, relegating extra info to
        ``.metadata``.

        Parameters
        ----------
        iocdict : dict
            IOC information dictionary.
        macros : dict, optional
            Additional macros to use at startup.
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
    context: FullLoadContext
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
    """
    A field with a value, as part of a EPICS V3 RecordInstance.
    """
    dtype: str
    name: str
    value: Any
    context: FullLoadContext

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """field({{name}}, "{{value}}")""",
        "console-verbose": textwrap.dedent(
            """\
            field({{name}}, "{{value}}")  # {{dtype}}
            {%- if context %}; {{context[-1]}}{% endif %}\
            """.rstrip(),
        ),
        "file": """
            field({{name}}, {{ _json_dump(value) }})
        """.strip(),
    }

    def update_from_record_type(
        self,
        record_type: RecordType
    ):
        """Update field information given dbd-provided information."""
        record_type_field = record_type.fields.get(self.name, None)
        if record_type_field is not None:
            self.dtype = record_type_field.type

    def update_unknowns(
        self,
        other: RecordField,
        *,
        unknown_values: Optional[Sequence[str]] = None,
    ):
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


# field1, field2, options (CA, CP, CPP, etc.)
FieldRelation = Tuple[RecordField, RecordField, List[str]]

PVRelations = Dict[
    str, Dict[str, List[FieldRelation]]
]


ScriptPVRelations = Dict[
    str, Dict[str, List[str]]
]


def get_link_information(link_str: str) -> Tuple[str, List[str]]:
    """Get link information from a DBF_{IN,OUT,FWD}LINK value."""
    if isinstance(link_str, (dict, list)):
        raise ValueError("JSON and PVAccess links are a TODO (sorry!)")
    if not isinstance(link_str, str):
        raise ValueError(
            f"Unexpected and supported type for get_link_information: "
            f"{type(link_str)}"
        )

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

    link_details = additional_info.split()
    return link_str, link_details


LINK_TYPES = {"DBF_INLINK", "DBF_OUTLINK", "DBF_FWDLINK"}


@dataclass
class RecordInstanceSummary:
    """An abbreviated form of :class:`RecordInstance`."""

    context: FullLoadContext
    name: str
    record_type: str
    # fields: Dict[str, RecordField]
    info: Dict[StringWithContext, Any] = field(default_factory=dict)
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


class UnquotedString(str):
    """
    An unquoted string token found when loading a database file.
    May be a linter warning.
    """
    ...


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
    """
    Part of a PVAccess group which references another record.
    """
    context: FullLoadContext
    #: THe name of this field.
    name: str = ""
    #: The referenced record name.
    record_name: str = ""
    #: The referenced record's field.
    field_name: str = ""
    #: Metadata from the field definition.
    metadata: Dict[str, str] = field(default_factory=dict)

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """\
PVAFieldReference: {{ record_name }}.{{ field_name }}
                 - {{ metadata }}
""",
        "file": "",
    }


AnyField = Union[RecordField, PVAFieldReference]


@dataclass
class DatabaseMenu:
    """An enumeration (menu) from a dbd file."""
    context: FullLoadContext
    #: The name of the menu.
    name: str
    #: Possible options for the menu - user-facing string identifier to
    #: internal identifier.
    choices: Dict[str, str]

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "file": textwrap.dedent(
            """\
            menu({{ name }}) {
            {% for name, choice in choices.items() %}
            {{ _indent }}choice({{ name }}, "{{ choice }}")
            {% endfor %}
            }
            """.rstrip(),
        ),
    }


@dataclass
class DatabaseDevice:
    """A per-record-type device definition, part of a dbd file."""
    record_type: str
    link_type: str
    dset_name: str
    choice_string: str

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "file": textwrap.dedent(
            """\
            device({{ record_type }}, {{ link_type }}, {{ dset_name }}, "{{ choice_string }}")
            """.rstrip(),
        ),
    }


@apischema.fields.with_fields_set
@dataclass
class RecordTypeField:
    """
    An EPICS V3 RecordType field definition, part of a database definition (dbd).
    """
    context: FullLoadContext
    #: Record type name.
    name: str
    #: The data type (e.g., DBF_STRING)
    type: str
    #: Access security level (ASL0, ASL1, or None)
    asl: Optional[str] = None
    #: Initial value for the field.
    initial: Optional[str] = None
    #: Grouping for the field in user interfaces.
    promptgroup: Optional[str] = None
    #: User interface information about the field.
    prompt: Optional[str] = None
    #: "Special" settings such as SPC_NOMOD (no write access)
    #: SPC_NOMOD      Field must not be modified
    #: SPC_DBADDR     db_name_to_addr must call cvt_dbaddr
    #: SPC_SCAN       scan related field is being changed
    #: SPC_ALARMACK   Special Alarm Acknowledgement
    #: SPC_AS         Access Security
    #: SPC_ATTRIBUTE  psuedo field, i.e. attribute field
    #:                useful when record support must be notified of a field
    #:                changing value
    #: SPC_MOD        used by all records that support a reset field
    #: SPC_RESET      The res field is being modified
    #:
    #: Specific to conversion:
    #: SPC_LINCONV  A linear conversion field is being changed
    #:
    #: Specific to calculation records
    #: SPC_CALC     The CALC field is being changed
    special: Optional[str] = None
    #: Process passive.
    pp: Optional[str] = None
    #: Process passive. TURE/FALSE.
    interest: Optional[str] = None
    #: Base: e.g., HEX
    base: Optional[str] = None
    #: Number of elements.
    size: Optional[str] = None
    #: Extra debug information.
    extra: Optional[str] = None
    #: Enum (menu) options for the field.
    menu: Optional[str] = None
    #: Property- YES/NO
    prop: Optional[str] = None
    # -> bundle the remainder in "body", even if unrecognized
    body: Dict[str, str] = field(default_factory=dict)

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "file": textwrap.dedent(
            """\
            field({{ name }}, {{ type }}) {
            {{ obj._get_file_repr() | indent(_fmt.indent) }}
            }
            """.rstrip(),
        ),
    }

    def _get_file_repr(self) -> str:
        # This is too slow to let jinja take care of....
        def get_value_repr(value: str):
            if isinstance(value, UnquotedString):
                return str(value)
            return f'"{value}"'

        return "\n".join(
            f"{attr}({get_value_repr(value)})"
            for attr, value in self.get_all_set_entries().items()
        )

    def get_all_set_entries(self) -> Dict[str, str]:
        """
        Get all field entries that have been set in the database definition.

        Returns
        -------
        dict
            e.g., {"initial": "5"}
        """
        entries = {}
        for attr in (
            # Order defined in dbStaticLib.c
            "prompt",
            "initial",
            "promptgroup",
            "special",
            "extra",
            "menu",
            "size",
            "pp",
            "prop",
            "base",
            "interest",
            "asl",
        ):
            value = getattr(self, attr)
            if value is not None:
                entries[attr] = value
        entries.update(self.body)
        return entries


@dataclass
class RecordType:
    """
    An EPICS V3 record type definition, part of a database definition (dbd).
    """
    context: FullLoadContext
    name: str
    cdefs: List[str] = field(default_factory=list)
    fields: Dict[str, RecordTypeField] = field(default_factory=dict)
    devices: List[DatabaseDevice] = field(default_factory=list)

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "file": textwrap.dedent(
            """\
            recordtype({{ name }}) {
            {% for cdef in cdefs %}
            {{ _indent }}%{{ cdef }}
            {% endfor %}
            {% for field_name, field in fields.items() %}
            {{ _indent }}field({{ field.name }}, {{ field.type }}) {
            {{ _indent }}{{ _indent }}{{ field._get_file_repr() | indent(_fmt.indent * 2) }}
            {{ _indent }}}
            {% endfor %}
            }
            """.rstrip(),
        ),
    }

    def get_links_for_record(
        self, record: RecordInstance
    ) -> Generator[Tuple[RecordField, str, List[str]], None, None]:
        """
        Get all links - in, out, and forward links - for the given record.

        Parameters
        ----------
        record : RecordInstance
            Additional information, if the database definition wasn't loaded
            with this instance.

        Yields
        ------
        field : RecordField
        link_text: str
        link_info: str
        """
        if record.record_type != self.name:
            raise ValueError("Record types do not match")

        for field_type_info in self.get_fields_of_type(*LINK_TYPES):
            field_instance = record.fields.get(field_type_info.name, None)
            if field_instance is None:
                continue
            elif isinstance(field_instance, PVAFieldReference):
                continue

            try:
                link, info = get_link_information(field_instance.value)
            except ValueError:
                continue
            yield field_instance, link, info

    def get_fields_of_type(self, *types: str) -> Generator[RecordTypeField, None, None]:
        """Get all fields of the matching type(s)."""
        for fld in self.fields.values():
            if fld.type in types:
                yield fld

    def get_link_fields(self) -> Generator[RecordTypeField, None, None]:
        """
        Get all link fields - in, out, and forward links.

        Yields
        ------
        field : RecordTypeField
        """
        yield from self.get_fields_of_type(*LINK_TYPES)


@dataclass
class RecordInstance:
    """
    An instance of a RecordType, loaded from a db file.
    """
    context: FullLoadContext
    #: The name of the record.
    name: str
    #: The record type name.
    record_type: str
    #: Whether or not there is corresponding information in the dbd file.
    has_dbd_info: bool = False
    #: Field information - field name to details.  May be either a V3
    #: RecordField or a PVAFieldReference.
    fields: Dict[str, AnyField] = field(default_factory=dict)
    #:
    info: Dict[StringWithContext, Any] = field(default_factory=dict)
    metadata: Dict[StringWithContext, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    is_grecord: bool = False
    is_pva: bool = False

    # For the convenience of downstream clients, redundantly keep track of the
    # associated IOC:
    owner: str = ""

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": textwrap.dedent(
            """\
            record({ record_type }}, "{{ name }}") {
            {% if owner %}
            {{ _indent }}# Part of {{ owner }}
            {% endif %}
            {% for ctx in context %}
            {{ _indent }}# {{ ctx }}
            {% endfor %}
            {% for name, field_inst in fields.items() | sort %}
            {{ _indent }}{{ render_object(field_inst, "console") | indent(_fmt.indent) }}
            {% endfor %}
            }
            """.rstrip()
        ),
        "file": textwrap.dedent(
            """\
            {% if is_grecord %}
            grecord({{ record_type }}, "{{ name }}") {
            {% else %}
            record({{ record_type }}, "{{ name }}") {
            {% endif %}
            {% for alias in aliases %}
            {{ _indent }}alias("{{ alias }}")
            {% endfor %}
            {% for name, field_inst in fields.items() | sort %}
            {{ _indent }}{{ render_object(field_inst, "file") | indent(_fmt.indent) }}
            {% endfor %}
            {% for name, info_value in info.items() | sort %}
            {{ _indent }}info({{ name }}, {{ _json_dump(info_value) | indent(_fmt.indent) }})
            {% endfor %}
            }
            """.rstrip()
        ),
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
    ) -> Generator[Tuple[RecordField, str, List[str]], None, None]:
        """
        Get all links - in, out, and forward links - for this record.

        Requires that a dbd file was loaded when the record was created.
        Alternatively, see :func:`RecordType.get_links_for_record`.

        Yields
        ------
        field : RecordField
        link_text: str
        link_info: str
        """
        for fld in self.get_fields_of_type(*LINK_TYPES):
            try:
                link, info = get_link_information(fld.value)
            except ValueError:
                continue
            yield fld, link, info

    def to_summary(self) -> RecordInstanceSummary:
        """Return a summarized version of the record instance."""
        return RecordInstanceSummary.from_record_instance(self)

    def update(self, other: RecordInstance) -> List[LinterMessage]:
        """
        Update this record instance with another.

        TODO: This may not do exactly what an IOC would do.
        TODO: Return type?
        """
        if other.is_pva != self.is_pva:
            return [
                LinterError(
                    name="combine_pva_and_v3",
                    context=tuple(self.context) + tuple(other.context),
                    message="Cannot combine PVA group with V3 record"
                )
            ]
        self.context = remove_redundant_context(
            tuple(self.context) + tuple(other.context)
        )
        self.info.update(other.info)
        self.metadata.update(other.metadata)
        self.fields.update(other.fields)
        self.aliases.extend(
            [alias for alias in other.aliases if alias not in self.aliases]
        )

        self.has_dbd_info = self.has_dbd_info or other.has_dbd_info
        if self.record_type != other.record_type:
            return [
                LinterError(
                    name="record_type_mismatch",
                    context=self.context,
                    message=(
                        f"Record type mismatch in provided database files: "
                        f"{self.name} {self.record_type} {other.record_type}"
                    ),
                )
            ]

        return []


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
                apischema.identity, source=cls, target=AsynPortBase
            )
        )

        # Only AsynPortBase serializer must be registered (and updated for each
        # subclass) as a Union, and not be inherited
        AsynPortBase._union = (
            cls if AsynPortBase._union is None else Union[AsynPortBase._union, cls]
        )
        apischema.serializer(
            apischema.conversions.Conversion(
                apischema.identity,
                source=AsynPortBase,
                target=AsynPortBase._union,
                inherited=False,
            )
        )


@dataclass
class ShellStateHandler:
    """A helper to work with interpreting commands from shell scripts."""
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
        "console": """{{ render_object(instance, "console") }}""",
        "file": """{{ render_object(instance, "file") }}""",
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
        "console": textwrap.dedent(
            """\
            {{ name }}:
            {{ _indent }}{Owner: {{ present }}
            {{ _indent }}{IOC: {{ render_object(ioc, "console") }}
            {% if record %}
            {{ _indent }}{{ render_object(record, "console") | indent(_fmt.indent)}}
            {% endif %}
            {% if pva_group %}
            {{ _indent }}{{ render_object(pva_group, "console") | indent(_fmt.indent)}}
            {% endif %}
            }
            """.rstrip()
        ),
        "file": textwrap.dedent(
            """\
            {{ name }}:
            {{ _indent }}{Owner: {{ present }}
            {{ _indent }}{IOC: {{ render_object(ioc, "file") }}
            {% if record %}
            {{ _indent }}{{ render_object(record, "file") | indent(_fmt.indent)}}
            {% endif %}
            {% if pva_group %}
            {{ _indent }}{{ render_object(pva_group, "file") | indent(_fmt.indent)}}
            {% endif %}
            }
            """.rstrip(),
        ),
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

    new_context = []
    for ctx in full_context:
        is_specific = ctx.name not in zero_line_files or ctx.line > 0
        if is_specific and ctx not in new_context:
            new_context.append(ctx)
    return tuple(new_context)
