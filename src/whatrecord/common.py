import dataclasses
import logging
import os
import pathlib
import typing
from dataclasses import field
from typing import ClassVar, Dict, List, Tuple

if typing.TYPE_CHECKING:
    from .asyn import AsynPort
    from .db import DbdFile, LinterResults
    from .iocsh import IOCShellInterpreter
    from .macro import MacroContext


logger = logging.getLogger(__name__)


@dataclasses.dataclass(repr=False)
class LoadContext:
    name: str
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"

    def freeze(self):
        return FrozenLoadContext(self.name, self.line)


@dataclasses.dataclass(repr=False, frozen=True)
class FrozenLoadContext:
    name: str
    line: int

    def __repr__(self):
        return f"{self.name}:{self.line}"


@dataclasses.dataclass
class IocshCommand:
    context: LoadContext
    command: str


@dataclasses.dataclass
class IocshResult:
    context: LoadContext
    line: str
    outputs: List[str]
    argv: List[str]
    error: str
    redirects: Dict[str, Dict[str, str]]
    result: object


@dataclasses.dataclass
class IocshScript:
    path: str
    lines: Tuple[IocshResult, ...]


@dataclasses.dataclass
class LinterMessage:
    name: str
    file: str
    line: int
    message: str


@dataclasses.dataclass
class LinterWarning(LinterMessage):
    ...


@dataclasses.dataclass
class LinterError(LinterMessage):
    ...


@dataclasses.dataclass
class ShortLinterResults:
    load_count: int
    errors: List[LinterError]
    warnings: List[LinterWarning]

    @classmethod
    def from_full_results(cls, results: "LinterResults"):
        return cls(
            load_count=len(results.recinst),
            errors=results.errors,
            warnings=results.warnings,
        )


@dataclasses.dataclass
class RecordField:
    dtype: str
    name: str
    value: str
    context: Tuple[LoadContext]

    _jinja_format_: ClassVar[dict] = {
        "console": """field({{name}}, "{{value}}")""",
        "console-verbose": """\
field({{name}}, "{{value}}")  # {{dtype}}{% if context %}; {{context[-1]}}{% endif %}\
""",
    }


def get_link_information(link_str: str) -> Tuple[str, str]:
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


@dataclasses.dataclass
class RecordInstance:
    context: Tuple[LoadContext]
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
        for fld in self.fields.values():
            if fld.dtype in types:
                yield fld

    def get_links(self):
        """Get all links."""
        for fld in self.get_fields_of_type(*LINK_TYPES):
            try:
                link, info = get_link_information(fld.value)
            except ValueError:
                continue
            yield fld, link, info


@dataclasses.dataclass
class WhatRecord:
    owner: str
    instance: RecordInstance
    asyn_ports: List["AsynPort"]
    # TODO:
    # - IOC host info, port?
    # - gateway rule matches?


@dataclasses.dataclass
class ShellStateBase:
    prompt: str = "epics>"
    variables: dict = field(default_factory=dict)
    string_encoding: str = "latin-1"
    macro_context: "MacroContext" = None
    standin_directories: Dict[str, str] = field(default_factory=dict)
    working_directory: pathlib.Path = field(default_factory=lambda: pathlib.Path.cwd())
    database_definition: "DbdFile" = None
    database: Dict[str, RecordInstance] = field(default_factory=dict)
    load_context: List[LoadContext] = field(default_factory=list)
    asyn_ports: Dict[str, object] = field(default_factory=dict)
    shell: "IOCShellInterpreter" = None
    loaded_files: Dict[str, pathlib.Path] = field(default_factory=dict)

    def __post_init__(self):
        if self.macro_context is None:
            from .macro import MacroContext
            self.macro_context = MacroContext()

    def get_asyn_port_from_record(self, inst: RecordInstance):
        rec_field = inst.fields.get("INP", inst.fields.get("OUT", None))
        if rec_field is None:
            return

        value = rec_field.value.strip()
        if value.startswith("@asyn"):
            try:
                asyn_args = value.split("@asyn")[1].strip(" ()")
                asyn_port, *_ = asyn_args.split(",")
                return self.asyn_ports.get(asyn_port.strip(), None)
            except Exception:
                logger.debug("Failed to parse asyn string", exc_info=True)

    def get_frozen_context(self):
        if not self.load_context:
            return tuple()
        return tuple(ctx.freeze() for ctx in self.load_context)

    def handle_command(self, command, *args):
        command = {
            "#": "comment",
        }.get(command, command)
        handler = getattr(self, f"handle_{command}", None)
        if handler is not None:
            return handler(*args)
        return self.unhandled(command, args)
        # return f"No handler for handle_{command}"

    def _fix_path(self, filename: str):
        if os.path.isabs(filename):
            for from_, to in self.standin_directories.items():
                if filename.startswith(from_):
                    _, suffix = filename.split(from_, 1)
                    return pathlib.Path(to + suffix)

        return self.working_directory / filename

    def unhandled(self, command, args):
        ...
        # return f"No handler for handle_{command}"
