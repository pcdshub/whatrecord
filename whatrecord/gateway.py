#!/usr/bin/env python3.8
import argparse
import io
import logging
import pathlib
import re
import sys
import typing
from typing import Dict, Generator, List, Optional, Tuple, Union

from .common import FullLoadContext, LoadContext, dataclass
from .util import get_bytes_sha256, get_file_sha256

MODULE_PATH = pathlib.Path(__file__).parent.resolve()
RE_WHITESPACE = re.compile(r"\s+")
logger = logging.getLogger(__name__)


@dataclass
class Token:
    """Token base class, making up a PVList."""

    line: str
    lineno: int

    @classmethod
    def from_line(cls, line, lineno):
        return cls(line=line, lineno=lineno)


@dataclass
class Setting(Token):
    """A token representing a configuration setting."""

    SETTINGS = {
        "evaluation",
    }

    line: str
    setting: Optional[str] = None
    values: Optional[List[str]] = None

    @classmethod
    def from_line(cls, line, lineno):
        setting, *values = line.split(" ")
        return cls(line=line, lineno=lineno, setting=setting, values=values)


@dataclass
class Comment(Token):
    """A token representing a comment line."""


@dataclass
class Expression(Token):
    """A token with a valid regular expression."""

    expr: str
    details: List[str]
    regex: typing.Pattern

    @classmethod
    def from_line(cls, line, lineno):
        line = RE_WHITESPACE.sub(line.strip(), " ")
        expr, *details = line.split(" ")
        try:
            regex = re.compile(expr)
        except Exception as ex:
            return BadExpression(
                line=line,
                lineno=lineno,
                expr=expr,
                details=details,
                exception=(type(ex).__name__, str(ex)),
            )
        return cls(line=line, lineno=lineno, expr=expr, details=details, regex=regex)

    def match(self, name):
        if self.regex is not None:
            return self.regex.match(name)


@dataclass
class BadExpression(Token):
    """A token with a bad regular expression."""

    expr: str
    details: List[str]
    exception: Tuple[str, str]


@dataclass
class PVList:
    """A PVList container."""

    identifier: Optional[str] = None
    tokenized_lines: Optional[List[Token]] = None
    hash: Optional[str] = None

    def find(
        self, cls: typing.Type
    ) -> Generator[Tuple[Optional[Comment], Expression], None, None]:
        context = None
        for line in self.tokenized_lines:
            if isinstance(line, Comment):
                context = line
            elif isinstance(line, cls):
                yield context, line

    def match(
        self, name: str
    ) -> Generator[Tuple[Optional[Comment], Expression], None, None]:
        context = None
        for context, expr in self.find(Expression):
            m = expr.match(name)
            if m:
                yield context, expr

    @staticmethod
    def tokenize(line, lineno=0) -> Optional[Token]:
        line = line.strip()
        if not line:
            return
        if line.startswith("#"):
            return Comment.from_line(line, lineno=lineno)
        word, *_ = line.split(" ")
        if word.lower() in Setting.SETTINGS:
            return Setting.from_line(line, lineno=lineno)
        # if '*' not in word and ':' not in word:
        #     print('hmm', line)
        return Expression.from_line(line, lineno=lineno)

    @classmethod
    def from_file_obj(cls, fp, identifier=None):
        lines = []
        contents = fp.read()
        contents_hash = get_bytes_sha256(contents.encode("utf-8"))
        for lineno, line in enumerate(contents.splitlines(), 1):
            tok = PVList.tokenize(line, lineno=lineno)
            if tok is not None:
                lines.append(tok)
        return cls(identifier, lines, hash=contents_hash)

    @classmethod
    def from_file(cls, fn):
        with open(fn, "rt") as fp:
            return cls.from_file_obj(fp, identifier=fn.name)


def create_arg_parser():
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="pvlist name matching and linting tool",
    )
    parser.add_argument("--lint", action="store_true", help="Lint regular expressions")
    parser.add_argument(
        "--pvlists",
        type=str,
        nargs="*",
        help="Specific pvlists to check (empty for all)",
    )
    parser.add_argument(
        "--hide-context", action="store_true", help="Hide comment context"
    )
    parser.add_argument(
        "--remove-any", action="store_true", help="Remove '.*' from results"
    )
    parser.add_argument("names", nargs="*", type=str, help="PV names to match")
    return parser


def run_lint(pvlists: List[PVList], show_context=False):
    """
    Lint the given PVLists, looking for invalid regular expressions.

    Parameters
    ----------
    pvlists : List[PVList]
        The PVLists to check
    show_context : bool, optional
        Show comment context for bad lines.
    """
    context = None
    for pvlist in pvlists:
        for context, expr in pvlist.find(BadExpression):
            print_match(pvlist, context, expr, show_context=show_context)


def print_match(
    pvlist: PVList,
    context: Optional[Comment],
    expr: Union[Expression, BadExpression],
    show_context: bool = True,
    file=sys.stdout,
):
    """
    Print a match to stdout.

    Parameters
    ----------
    pvlist : PVList
        The PVList container.
    context : Optional[Comment]
        The comment context of the match.
    expr : Union[Expression, BadExpression]
        The expression that matched.
    show_context : bool
        Option to show or hide context.
    file : file-like object

    """
    ident = pvlist.identifier
    if context is not None and show_context:
        ctx = f" <<Comment: {ident}:{context.lineno}: {context.line}>>"
    else:
        ctx = ""

    print(
        f"{ident}:{expr.lineno}: {expr.expr!r} {' '.join(expr.details)}{ctx}", file=file
    )
    if isinstance(expr, BadExpression):
        print(
            f"{ident}:{expr.lineno}: {expr.expr!r}: ERROR: {expr.exception}", file=file
        )


def run_match_and_aggregate(
    pvlists: List[PVList],
    names: List[str],
    show_context: bool = True,
    remove_any: bool = False,
):
    """
    Match ``names`` against all PVLists, and aggregate by matching rule sets.

    Parameters
    ----------
    pvlists : List[PVList]
        The list of PVLists.
    name : List[str]
        PV name to match.
    show_context : bool
        Show comment context of the matching line.
    remove_any : bool
        Remove catch-all '.*' from lines.
    """
    by_name = {}
    for name in names:
        with io.StringIO() as fp:
            for pvlist in pvlists:
                for context, expr in pvlist.match(name):
                    if expr.expr == ".*" and remove_any:
                        continue

                    print_match(
                        pvlist, context, expr, show_context=show_context, file=fp
                    )

            by_name[name] = fp.getvalue() or "No matches"

    by_rule = {}
    for name, rules in by_name.items():
        if rules not in by_rule:
            by_rule[rules] = set()
        by_rule[rules].add(name)

    for rule, names in by_rule.items():
        print("-" * max(len(line) for line in rule.splitlines()))
        print(rule.strip())
        print("-" * max(len(line) for line in rule.splitlines()))
        for name in sorted(names):
            print(name)
        print()

    return by_rule


def run_match(
    pvlists: List[PVList],
    name: str,
    show_context: bool = True,
    remove_any: bool = False,
):
    """
    Match ``name`` against all PVLists.

    Parameters
    ----------
    pvlists : List[PVList]
        The list of PVLists.
    name : List[str]
        PV name to match.
    show_context : bool
        Show comment context of the matching line.
    remove_any : bool
        Remove catch-all '.*' from lines.
    """
    for pvlist in pvlists:
        for context, expr in pvlist.match(name):
            if expr.expr == ".*" and remove_any:
                continue

            print_match(pvlist, context, expr, show_context=show_context)


@dataclass
class PVListMatch:
    context: FullLoadContext
    comment_context: Optional[FullLoadContext]
    comment: Optional[str]
    expression: str
    details: List[str]


@dataclass
class PVListMatches:
    name: str
    matches: List[PVListMatch]


class GatewayConfig:
    pvlists: Dict[pathlib.Path, PVList]

    def __init__(self, path: Union[str, pathlib.Path], glob_str: str = "*.pvlist"):
        path = pathlib.Path(path).resolve()
        if path.is_file():
            filenames = [path]
        else:
            filenames = [p.resolve() for p in path.glob(glob_str)]

        self.pvlists = {
            filename: PVList.from_file(filename) for filename in filenames
        }

    def _update(self, filename):
        """Update a gateway configuration file."""
        self.pvlists[filename] = PVList.from_file(filename)

    def update_changed(self):
        """Update any changed files."""
        for filename, pvlist in self.pvlists.items():
            if get_file_sha256(filename) != pvlist.hash:
                logger.info("Updating changed gateway file: %s", filename)
                self._update(filename)

    def get_matches(self, name: str, remove_any: bool = True):
        def get_comment_context(fn, context) -> Optional[FullLoadContext]:
            if context is not None:
                return (LoadContext(str(fn), context.lineno),)

        matches = [
            PVListMatch(
                context=(LoadContext(str(fn), expr.lineno),),
                comment_context=get_comment_context(fn, context),
                comment=context.line if context is not None else None,
                expression=expr.expr,
                details=expr.details,
            )
            for fn, pvlist in self.pvlists.items()
            for context, expr in pvlist.match(name)
            if expr.expr != ".*" or not remove_any
        ]

        return PVListMatches(
            name=name,
            matches=matches,
        )

    def get_linter_results(self):
        # TODO: unused
        return [
            PVListMatch(context=context, expression=expr.expr, details=expr.details)
            for _, pvlist in self.pvlists.items()
            for context, expr in pvlist.find(BadExpression)
        ]
