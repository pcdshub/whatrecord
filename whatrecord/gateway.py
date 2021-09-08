#!/usr/bin/env python3.8
import argparse
import logging
import pathlib
import re
import typing
from dataclasses import dataclass, field
from typing import Dict, Generator, List, Optional, Tuple, Union

import apischema
import lark

from . import transformer
from .common import FullLoadContext, StringWithContext, context_from_lark_token
from .util import get_bytes_sha256, get_file_sha256

MODULE_PATH = pathlib.Path(__file__).parent.resolve()
logger = logging.getLogger(__name__)


@dataclass
class Rule:
    """A PVList rule (base class)."""
    context: FullLoadContext
    pattern: str
    command: str
    regex: typing.Pattern = field(
        default=None,
        metadata=apischema.metadata.skip
    )
    header: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.regex is None:
            try:
                self.regex = re.compile(self.pattern)
            except Exception as ex:
                self.metadata["error"] = (
                    f"Invalid regex. {ex.__class__.__name__}: {ex}"
                )

    def match(self, name):
        """Match a pv name against this rule."""
        if self.regex is not None:
            return self.regex.fullmatch(name)


@dataclass
class AccessSecurity:
    """A PVList rule access security settings."""
    group: Optional[str] = None
    level: Optional[str] = None


@dataclass
class AliasRule(Rule):
    """Rule to alias the pattern to a PV (or PVs)."""
    pvname: str = ""
    access: Optional[AccessSecurity] = None


@dataclass
class DenyRule(Rule):
    """Rule to deny access to a PV pattern."""
    hosts: List[str] = field(default_factory=list)


@dataclass
class AllowRule(Rule):
    """Rule to allow access to a PV pattern."""
    access: Optional[AccessSecurity] = None


@lark.visitors.v_args(inline=True)
class _PVListTransformer(lark.visitors.Transformer_InPlaceRecursive):
    fn: str
    contents_hash: str
    comments: List[str]

    def __init__(self, fn, contents_hash: str, comments: List[str]):
        super().__init__(visit_tokens=False)
        self.fn = str(fn)
        self.contents_hash = contents_hash
        self.comments = comments

    def get_header_comments(self) -> str:
        """Get all comments at the top of the file."""
        results = []
        lineno = 0
        for comment in self.comments:
            if comment.context[0].line == lineno + 1:
                results.append(str(comment).lstrip("# "))
                lineno += 1
            else:
                break

        return "\n".join(results)

    def get_recent_comments(self, lineno: int) -> str:
        """Get all comments just before the given line."""
        results = []
        for comment in reversed(self.comments):
            comment_line = comment.context[0].line
            if comment_line == lineno - 1:
                results.append(str(comment).lstrip("# "))
                lineno -= 1
            elif comment_line > lineno:
                # lexer can get ahead of this line; keep going.
                ...
            else:
                break

        return "\n".join(reversed(results))

    def pvlist(self, *items):
        rules = []
        evaluation = None
        for item in items:
            if isinstance(item, Rule):
                rules.append(item)
            elif isinstance(item, str):
                evaluation = item
            else:
                raise ValueError("unexpected top-level item?")

        return PVList(
            filename=self.fn,
            evaluation_order=evaluation,
            rules=list(rules),
            header=self.get_header_comments(),
            hash=self.contents_hash,
        )

    def evaluation_order(self, first, _, second) -> str:
        return f"{first.upper()}, {second.upper()}"

    def evaluation(self, _evaluation, _order, order, *_):
        return order

    pattern = transformer.stringify
    pvname = transformer.stringify
    hosts = transformer.listify
    host = transformer.stringify

    def allow(
        self,
        pattern: str,
        allow_token: lark.Token,
        asg_asl: Optional[AccessSecurity] = None,
        *_
    ) -> AllowRule:
        return AllowRule(
            context=context_from_lark_token(self.fn, allow_token),
            command=str(allow_token).upper(),
            pattern=pattern,
            access=asg_asl if _ else None,
            header=self.get_recent_comments(allow_token.line),
        )

    def alias(
        self,
        pattern: str,
        alias_token: lark.Token,
        pvname: str,
        asg_asl: Optional[AccessSecurity] = None,
        *_
    ) -> AliasRule:
        return AliasRule(
            context=context_from_lark_token(self.fn, alias_token),
            command=str(alias_token).upper(),
            pattern=pattern,
            pvname=pvname,
            access=asg_asl if _ else None,
            header=self.get_recent_comments(alias_token.line),
        )

    def deny(
        self,
        pattern: str,
        deny_token: lark.Token,
        from_hosts: Optional[List[str]] = None,
        *_
    ) -> DenyRule:
        hosts = None
        if from_hosts and str(from_hosts).strip():
            hosts = from_hosts

        return DenyRule(
            context=context_from_lark_token(self.fn, deny_token),
            command=str(deny_token).upper(),
            pattern=pattern,
            hosts=hosts or [],
            header=self.get_recent_comments(deny_token.line),
        )

    def asg_asl(self, group: str, level: Optional[str] = None) -> AccessSecurity:
        return AccessSecurity(group=group, level=level)

    asg = transformer.stringify
    asl = transformer.stringify


@dataclass
class PVList:
    """A PVList container."""
    filename: Optional[str] = None
    evaluation_order: Optional[str] = None
    rules: List[Rule] = field(default_factory=list)
    hash: Optional[str] = None
    header: str = ""
    comments: List[lark.Token] = field(
        default_factory=list,
        metadata=apischema.metadata.skip,
    )

    def find(
        self, cls: typing.Type
    ) -> Generator[Rule, None, None]:
        """Yield matching rule types."""
        for rule in self.rules:
            if isinstance(rule, cls):
                yield rule

    def match(
        self, name: str
    ) -> Generator[Tuple[Rule, List[str]], None, None]:
        """Yield matching rules."""
        for rule in self.rules:
            m = rule.match(name)
            if m:
                yield rule, list(m.groups())

    @classmethod
    def from_string(cls, contents: str, filename: Optional[str] = None):
        contents_hash = get_bytes_sha256(contents.encode("utf-8"))
        comments = []

        def add_comment(comment: lark.Token):
            comments.append(
                StringWithContext(
                    str(comment).lstrip("# "),
                    context=context_from_lark_token(filename, comment),
                )
            )

        grammar = lark.Lark.open_from_package(
            "whatrecord",
            "gateway.lark",
            search_paths=("grammar", ),
            parser="lalr",
            lexer_callbacks={"COMMENT": add_comment},
            transformer=_PVListTransformer(filename, contents_hash, comments),
        )

        # Sorry, the grammar isn't perfect: require a newline for rules
        pvlist: PVList = grammar.parse(f"{contents.strip()}\n")
        pvlist.comments = comments
        return pvlist

    @classmethod
    def from_file_obj(cls, fp, filename: Optional[str] = None):
        """Load a PVList from a file object."""
        filename = filename or getattr(fp, "name", str(id(fp)))
        return cls.from_string(fp.read(), filename=filename)

    @classmethod
    def from_file(cls, fn: Union[str, pathlib.Path]):
        """Load a PVList from a filename."""
        with open(fn, "rt") as fp:
            return cls.from_file_obj(fp, filename=str(fn))


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


@dataclass
class PVListMatch:
    filename: str
    rule: Rule
    groups: List[str]


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

    def get_matches(self, name: str, remove_any: bool = True) -> PVListMatches:
        """Get matches from any PVList given a PV name."""
        matches = [
            PVListMatch(
                filename=str(fn),
                rule=rule,
                groups=groups,
            )
            for fn, pvlist in self.pvlists.items()
            for rule, groups in pvlist.match(name)
            if rule.pattern != ".*" or not remove_any
        ]

        return PVListMatches(
            name=name,
            matches=matches,
        )
