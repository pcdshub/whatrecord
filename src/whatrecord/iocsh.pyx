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

from .common import IocshCommand, IocshResult, LoadContext, ShellStateBase
from .db import DbdFile, RecordField, RecordInstance
from .macro import MacroContext

logger = logging.getLogger(__name__)

def _get_redirect(redirects: dict, idx: int):
    if idx not in redirects:
        redirects[idx] = {"name": "", "mode": ""}
    return redirects[idx]


cdef class IOCShellInterpreter:
    NREDIRECTS: int = 5
    ifs: bytes = b" \t(),\r"

    cdef public object state

    def __init__(self, state: Optional[ShellStateBase] = None):
        if state is None:
            state = ShellStateBase()

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

    def parse(self, line: str, *, context=None) -> IocshResult:
        if context is None:
            context = tuple(ctx.freeze() for ctx in self.state.load_context)

        result = IocshResult(
            context=context,
            line=line,
            outputs=[],
            argv=None,
            error=None,
            redirects={},
            result=None,
        )
        # Skip leading whitespace
        line = line.lstrip()

        if not line.startswith("#-"):
            result.outputs.append(line)

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
                result.outputs.append(line)

        # * Ignore lines that became a comment or empty after macro expansion
        if not line or line.startswith('#'):
            return result

        split = self.split_words(line)
        result.argv = split["argv"]
        result.redirects = split["redirects"]
        result.error = split["error"]
        return result

    def interpret_shell_line(self, line, recurse=True, raise_on_error=False):
        shresult = self.parse(line)
        input_redirects = [
            (fileno, redir) for fileno, redir in shresult.redirects.items()
            if redir["mode"] == "r"
        ]
        if shresult.error:
            ...

        elif input_redirects:
            fileno, redir = input_redirects[0]
            if recurse:
                try:
                    filename = self.state._fix_path(redir["name"])
                    with open(filename, "rt") as fp_redir:
                        yield from self.interpret_shell_script(
                            fp_redir, recurse=recurse
                        )
                    return
                except FileNotFoundError:
                    shresult.error = f"File not found: {filename}"
        elif shresult.argv:
            try:
                shresult.result = self.state.handle_command(*shresult.argv)
            except Exception as ex:
                if raise_on_error:
                    raise
                ex_details = traceback.format_exc()
                shresult.error = f"Failed to execute: {ex}:\n{ex_details}"

            if isinstance(shresult.result, IocshCommand):
                yield shresult
                yield from self.interpret_shell_line(
                    shresult.result.command, recurse=recurse
                )
                return
        yield shresult

    def interpret_shell_script(self, lines,
                               name="unknown",
                               recurse=True,
                               raise_on_error=False):
        load_ctx = LoadContext(name, 0)
        try:
            self.state.load_context.append(load_ctx)
            for lineno, line in enumerate(lines, 1):
                load_ctx.line = lineno
                yield from self.interpret_shell_line(
                    line,
                    recurse=recurse,
                    raise_on_error=raise_on_error,
                )
        finally:
            self.state.load_context.remove(load_ctx)
