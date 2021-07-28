"""
V3 Access Security file parsing.

Documentation from the application developer's guide are interspersed here
and in the classes below.

```
A brief summary of the Functional Requirements is:
    * Each field of each record type is assigned an access security level.
    * Each record instance is assigned to a unique access security group.
    * Each user is assigned to one or more user access groups.
    * Each node is assigned to a host access group.

For each access security group a set of access rules can be defined. Each rule
specifies:
    -  Access security level
    -  READ or READ/WRITE access.
    -  An optional list of User Access Groups or * meaning anyone.
    -  An optional list of Host Access Groups or * meaning anywhere.
    -  Conditions based on values of process variables
```
"""

from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import apischema
import lark

from .common import FullLoadContext, StringWithContext, context_from_lark_token
from .util import get_bytes_sha256

MODULE_PATH = pathlib.Path(__file__).parent.resolve()
logger = logging.getLogger(__name__)


@dataclass
class UserAccessGroup:
    """
    User Access Group.

    This is a list of user names. The list may be empty. A user name may appear
    in more than one UAG. To match, a user name must be identical to the user
    name read by the CA client library running on the client machine. For
    vxWorks clients, the user name is usually taken from the user field of the
    boot parameters.
    """
    context: FullLoadContext
    comments: str
    name: str
    users: List[str]


@dataclass
class HostAccessGroup:
    """
    Host Access Group.

    This is a list of host names. It may be empty. The same host name can
    appear in multiple HAGs. To match, a host name must match the host name
    read by the CA client library running on the client machine; both names are
    converted to lower case before comparison however. For vxWorks clients, the
    host name is usually taken from the target name of the boot parameters.
    """
    context: FullLoadContext
    comments: str
    name: str
    hosts: List[str]


@apischema.fields.with_fields_set
@dataclass
class AccessSecurityRule:
    """
    Access Security Configuration rule, which defines access permissions.

    <level> must be 0 or 1. Permission for a level 1 field implies permission
    for level 0 fields.

    The permissions are NONE, READ, and WRITE. WRITE permission implies READ
    permission. The standard EPICS record types have all fields set to level 1
    except for VAL, CMD (command), and RES (reset). An optional argument
    specifies if writes should be trapped. See the section below on trapping
    Channel Access writes for how this is used. If not given the default is
    NOTRAPWRITE.

    UAG specifies a list of user access groups that can have the access
    privilege. If UAG is not defined then all users are allowed.

    HAG specifies a list of host access groups that have the access privilege.
    If HAG is not defined then all hosts are allowed.

    CALC is just like the CALC field of a calculation record except that the
    result must evaluate to TRUE or FALSE. The rule only applies if the
    calculation result is TRUE, where the actual test for TRUE is
    (0.99 < result < 1.01).

    Anything else is regarded as FALSE and will cause the rule to be ignored.
    Assignment statements are not permitted in CALC expressions here.
    """
    context: FullLoadContext
    comments: str
    level: int
    options: str
    log_options: Optional[str] = None
    users: Optional[List[str]] = None
    hosts: Optional[List[str]] = None
    calc: Optional[str] = None


@dataclass
class AccessSecurityGroup:
    context: FullLoadContext
    comments: str
    name: str
    inputs: Dict[str, str] = field(default_factory=dict)
    rules: List[AccessSecurityRule] = field(default_factory=list)


def _listify():
    """Transformer helper to listify *args."""
    @staticmethod
    def inner(*objects):
        return list(objects)
    return inner


def _listify_strings():
    """Transformer helper to listify *args and stringify each arg."""
    @staticmethod
    def inner(*objects):
        return list(str(obj) for obj in objects)
    return inner


def _stringify():
    """Transformer helper to stringify a single argument."""
    @staticmethod
    def inner(obj: lark.Token) -> str:
        return str(obj)
    return inner


def _pass_through():
    """Transformer helper to pass through an optional single argument."""
    @staticmethod
    def inner(obj: Optional[lark.Token] = None):
        return obj
    return inner


@lark.visitors.v_args(inline=True)
class _AcfTransformer(lark.visitors.Transformer):
    fn: str
    contents_hash: str
    comments: List[str]
    hosts: Dict[str, HostAccessGroup]
    users: Dict[str, UserAccessGroup]
    groups: Dict[str, AccessSecurityGroup]
    inputs: Dict[str, str]
    calc: Tuple[lark.Token, str]

    def __init__(self, fn, contents_hash: str, comments: List[str]):
        super().__init__(visit_tokens=False)
        self.fn = str(fn)
        self.contents_hash = contents_hash
        self.comments = comments
        self.hosts = {}
        self.users = {}
        self.groups = {}
        self.rule_info = {}
        self.rules = []
        self.inputs = {}
        self.calc = None

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

    uag_head = _stringify()
    uag_body = _pass_through()
    uag_user_list = _listify()
    uag_user_list_name = _stringify()

    def uag(self, uag_token, name, users=None):
        user_group = UserAccessGroup(
            context=context_from_lark_token(self.fn, uag_token),
            name=name,
            users=users or [],
            comments=self.get_recent_comments(uag_token.line),
        )
        self.users[user_group.name] = user_group

    hag_head = _stringify()
    hag_body = _pass_through()
    hag_host_list = _listify()
    hag_host_list_name = _stringify()

    def hag(self, hag_token, name, hosts=None):
        host_group = HostAccessGroup(
            context=context_from_lark_token(self.fn, hag_token),
            name=name,
            hosts=hosts or [],
            comments=self.get_recent_comments(hag_token.line),
        )
        self.hosts[host_group.name] = host_group

    def asg(self, asg_token, name, body=None):
        rules, self.rules = self.rules, []
        inputs, self.inputs = self.inputs, {}
        self.groups[str(name)] = AccessSecurityGroup(
            context=context_from_lark_token(self.fn, asg_token),
            comments=self.get_recent_comments(asg_token.line),
            rules=rules,
            name=name,
            inputs=inputs,
        )

    asg_head = _stringify()
    asg_body = _stringify()
    asg_body_list = _listify()
    asg_body_item = _pass_through()

    def rule_config(self, rule_token, head, body=None):
        rule_info, self.rule_info = self.rule_info, {}
        token_to_kwarg = {
            "UAG": "users",
            "HAG": "hosts",
            "CALC": "calc",
        }
        kwargs = {
            token_to_kwarg[key]: value
            for key, value in rule_info.items()
        }
        level, options, log_options = head
        if log_options is not None:
            kwargs["log_options"] = log_options

        if self.calc is not None:
            kwargs["calc"] = self.calc[1]
            self.calc = None

        rule = AccessSecurityRule(
            context=context_from_lark_token(self.fn, rule_token),
            comments=self.get_recent_comments(rule_token.line),
            level=level,
            options=options,
            **kwargs,
        )
        self.rules.append(rule)

    rule_body = _pass_through()
    rule_list = _listify()

    @staticmethod
    def rule_head(mandatory, options):
        level, log_options = mandatory
        return (level, log_options, options)

    @staticmethod
    def rule_head_mandatory(level, options):
        return (int(level), str(options))

    rule_head_options = _pass_through()
    rule_log_options = _stringify()

    rule_uag_list = _listify_strings()
    rule_hag_list = _listify_strings()

    def rule_uag(self, uag_token, users):
        self.rule_info[uag_token] = users

    def rule_hag(self, hag_token, hosts):
        self.rule_info[hag_token] = hosts

    def rule_calc(self, calc_token, calc_str):
        self.calc = (calc_token, str(calc_str).strip('" '))

    def inp_config(self, inp_token, link):
        self.inputs[inp_token] = str(link)

    @lark.visitors.v_args(tree=True)
    def asconfig(self, _):
        return AccessSecurityConfig(
            filename=self.fn,
            header=self.get_header_comments(),
            hash=self.contents_hash,
            hosts=self.hosts,
            users=self.users,
            groups=self.groups,
        )


@dataclass
class AccessSecurityConfig:
    """An Access Security Configuration file (ACF) container."""
    filename: Optional[str] = None
    hash: Optional[str] = None
    users: Dict[str, UserAccessGroup] = field(default_factory=dict)
    groups: Dict[str, AccessSecurityGroup] = field(default_factory=dict)
    hosts: Dict[str, HostAccessGroup] = field(default_factory=dict)
    header: str = ""
    comments: List[lark.Token] = field(
        default_factory=list,
        metadata=apischema.metadata.skip,
    )

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
            "access_security.lark",
            search_paths=("grammar", ),
            parser="lalr",
            lexer_callbacks={"COMMENT": add_comment},
            transformer=_AcfTransformer(filename, contents_hash, comments),
        )

        return grammar.parse(contents)

    @classmethod
    def from_file_obj(cls, fp, filename: Optional[str] = None):
        """Load a PVList from a file object."""
        filename = filename or getattr(fp, "name", str(id(fp)))
        return cls.from_string(fp.read(), filename=filename)

    @classmethod
    def from_file(cls, fn: Union[str, pathlib.Path]):
        """Load an ACF file from a filename."""
        with open(fn, "rt") as fp:
            return cls.from_file_obj(fp, filename=str(fn))
