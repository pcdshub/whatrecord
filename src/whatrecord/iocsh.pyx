# cython: language_level=3
import copy
import logging
import os
import pathlib
import traceback
import typing
from typing import Dict, List, Optional

cimport epicscorelibs
cimport epicscorelibs.Com

from .common import Context, IocshCommand
from .db import DbdFile, RecordField, RecordInstance
from .macro import MacroContext

logger = logging.getLogger(__name__)

def _get_redirect(redirects: dict, idx: int):
    if idx not in redirects:
        redirects[idx] = {"name": "", "mode": ""}
    return redirects[idx]


class StateBase:
    shell: "IOCShellInterpreter"
    prompt: str
    variables: dict
    string_encoding: str
    macro_context: MacroContext
    standin_directories: dict
    working_directory: pathlib.Path
    database_definition: DbdFile
    database: Dict[str, RecordInstance]
    load_context: List[Context]
    asyn_ports: Dict[str, object]

    def __init__(
        self,
        shell: Optional["IOCShellInterpreter"] = None,
        prompt: str = "epics>",
        string_encoding: str = "latin-1",
        variables: Optional[dict] = None,
    ):
        self.shell = shell
        self.prompt = prompt
        self.string_encoding = string_encoding
        self.variables = dict(variables or {})
        self.macro_context = MacroContext()
        self.standin_directories = {}
        self.working_directory = pathlib.Path.cwd()
        self.database_definition = None
        self.database = {}
        self.asyn_ports = {}
        self.load_context = []

    def get_asyn_port_from_record(self, inst: RecordInstance):
        field: RecordField = inst.fields.get("INP", inst.fields.get("OUT", None))
        if field is None:
            return

        value = field.value.strip()
        if value.startswith("@asyn"):
            try:
                asyn_args = value.split("@asyn")[1].strip(" ()")
                asyn_port, *_ = asyn_args.split(",")
                return self.asyn_ports.get(asyn_port.strip(), None)
            except Exception:
                logger.debug("Failed to parse asyn string", exc_info=True)

    def get_short_context(self):
        if not self.load_context:
            return None
        return self.load_context[-1].freeze()

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


cdef class IOCShellInterpreter:
    NREDIRECTS: int = 5
    ifs: bytes = b" \t(),\r"

    cdef public object state

    def __init__(self, state: Optional[StateBase] = None):
        if state is None:
            state = StateBase()

        self.state = state
        self.state.shell = self

    @property
    def string_encoding(self):
        """String encoding, for convenience."""
        return self.state.string_encoding

    cdef _decode_string(self, bytearr: bytearray):
        if 0 in bytearr:
            bytearr = bytearr[:bytearr.index(0)]
        return str(bytearr, self.string_encoding)

    cpdef split_words(self, input_line: str):
        cdef int EOF = -1
        cdef int inword = 0
        cdef int quote = EOF
        cdef int backslash = 0
        cdef int idx = 0
        cdef int idx_out = 0
        cdef int redirectFd = 1
        cdef dict redirects = {}
        cdef char c
        redirect = None
        word_starts = []

        # TODO: read more:
        # https://cython.readthedocs.io/en/latest/src/tutorial/strings.html
        cdef bytearray line = bytearray(input_line.encode(self.string_encoding))
        # Add in a null terminator as we might need it
        line.append(0)

        while idx < len(line):
            c = line[idx]
            idx += 1

            if quote == EOF and not backslash and c in self.ifs:
                sep = 1
            else:
                sep = 0

            if quote == EOF and not backslash:
                if c == b'\\':
                    backslash = 1
                    continue
                if c == b'<':
                    if redirect:
                        break

                    redirect = _get_redirect(redirects, 0)
                    sep = 1
                    redirect["mode"] = "r"

                if b'1' <= c <= b'9' and line[idx] == b'>':
                    redirectFd = c - b'0'
                    c = b'>'
                    idx += 1

                if c == b'>':
                    if redirect:
                        break
                    if redirectFd >= self.NREDIRECTS:
                        redirect = _get_redirect(redirects, 1)
                        break
                    redirect = _get_redirect(redirects, redirectFd)
                    sep = 1
                    if line[idx] == b'>':
                        idx += 1
                        redirect["mode"] = "a"
                    else:
                        redirect["mode"] = "w"

            if inword:
                if c == quote:
                    quote = EOF
                elif quote == EOF and not backslash:
                    if sep:
                        inword = 0
                        line[idx_out] = 0
                        idx_out += 1
                    elif c == b'"' or c == b"'":
                        quote = c
                    else:
                        line[idx_out] = c
                        idx_out += 1
                else:
                    line[idx_out] = c
                    idx_out += 1
            elif not sep:
                if (c == b'"' or c == b'\'') and not backslash:
                    quote = c
                if redirect:
                    if redirect["name"]:
                        break
                    redirect["name"] = idx_out
                    redirect = None
                else:
                    word_starts.append(idx_out)
                if quote == EOF:
                    line[idx_out] = c
                    idx_out += 1
                inword = 1
            backslash = 0

        if inword and idx_out < len(line):
            line[idx_out] = 0
            idx_out += 1

        # Python-only as we're not dealing with pointers to the string;
        # fix up redirect names by looking back at ``line``
        for _redir in redirects.values():
            if isinstance(_redir["name"], int):
                _redir["name"] = self._decode_string(line[_redir["name"]:])
            elif not _redir["name"]:
                error = f"Illegal redirection. ({_redir})"

        error = None

        if redirect is not None:
            error = f"Illegal redirection. ({redirect})"
        elif word_starts:
            if quote != EOF:
                error = f"Unbalanced quote. ({quote})"
            elif backslash:
                error = "Trailing backslash."

        return dict(
            # Python-only as we're not dealing with pointers to the string;
            # fix up argv words by looking back at the modified ``line``
            argv=[self._decode_string(line[word_start:]) for word_start in word_starts],
            redirects=redirects,
            error=error,
        )

    def parse(self, line: str):
        result = {
            "outputs": [],
            "argv": None,
            "error": None,
            "redirects": {},
        }
        # Skip leading whitespace
        line = line.lstrip()

        if not line.startswith("#-"):
            result["outputs"].append(line)

        if line.startswith('#'):
            # Echo non-empty lines read from a script.
            # Comments delineated with '#-' aren't echoed.
            return result

        line = self.state.macro_context.expand(line)

         # * Skip leading white-space coming from a macro
        line = line.lstrip()

         # * Echo non-empty lines read from a script.
         # * Comments delineated with '#-' aren't echoed.
        if not self.state.prompt:
            if not line.startswith('#-'):
                result["outputs"].append(line)

        # * Ignore lines that became a comment or empty after macro expansion
        if not line or line.startswith('#'):
            return result

        result.update(self.split_words(line))
        return result

    def interpret_shell_line(self, line, recurse=True, raise_on_error=False):
        info = self.parse(line)
        input_redirects = [
            (fileno, redir) for fileno, redir in info["redirects"].items()
            if redir["mode"] == "r"
        ]
        result = None
        if info["error"]:
            ...

        elif input_redirects:
            fileno, redir = input_redirects[0]
            if recurse:
                try:
                    filename = self.state._fix_path(redir["name"])
                    with open(filename, "rt") as fp_redir:
                        for info, result in self.interpret_shell_script(
                            fp_redir, recurse=recurse
                        ):
                            info["filename"] = filename
                            yield info, result
                    return
                except FileNotFoundError:
                    info["error"] = f"File not found: {filename}"
        elif info["argv"]:
            try:
                result = self.state.handle_command(*info["argv"])
            except Exception as ex:
                if raise_on_error:
                    raise
                ex_details = traceback.format_exc()
                info["error"] = f"Failed to execute: {ex}:\n{ex_details}"

            if isinstance(result, IocshCommand):
                yield info, result
                yield from self.interpret_shell_line(
                    result.command, recurse=recurse
                )
                return
        yield info, result

    def interpret_shell_script(self, fp: typing.IO[str], recurse=True,
                               raise_on_error=False):
        try:
            fn = getattr(fp, "name", "unknown")
            load_ctx = Context(fn, 0)
            self.state.load_context.append(load_ctx)
            for lineno, line in enumerate(fp.read().splitlines(), 1):
                load_ctx.line = lineno
                for info, result in self.interpret_shell_line(
                    line,
                    recurse=recurse,
                    raise_on_error=raise_on_error,
                ):
                    yield info, result
        finally:
            self.state.load_context.remove(load_ctx)
