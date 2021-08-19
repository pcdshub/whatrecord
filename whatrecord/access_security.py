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
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

import apischema
import lark

from . import transformer
from .common import (FullLoadContext, RecordInstance, ShellStateHandler,
                     StringWithContext, context_from_lark_token)
from .macro import MacroContext
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
    """An access security group."""
    context: FullLoadContext
    comments: str
    name: str
    inputs: Dict[str, str] = field(default_factory=dict)
    rules: List[AccessSecurityRule] = field(default_factory=list)


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

    uag_head = transformer.stringify
    uag_body = transformer.pass_through
    uag_user_list = transformer.listify
    uag_user_list_name = transformer.stringify

    def uag(self, uag_token: lark.Token, name, users=None):
        user_group = UserAccessGroup(
            context=context_from_lark_token(self.fn, uag_token),
            name=name,
            users=users or [],
            comments=self.get_recent_comments(uag_token.line),
        )
        self.users[user_group.name] = user_group

    hag_head = transformer.stringify
    hag_body = transformer.pass_through
    hag_host_list = transformer.listify
    hag_host_list_name = transformer.stringify

    def hag(self, hag_token: lark.Token, name, hosts=None):
        host_group = HostAccessGroup(
            context=context_from_lark_token(self.fn, hag_token),
            name=name,
            hosts=hosts or [],
            comments=self.get_recent_comments(hag_token.line),
        )
        self.hosts[host_group.name] = host_group

    def asg(self, asg_token: lark.Token, name, body=None):
        rules, self.rules = self.rules, []
        inputs, self.inputs = self.inputs, {}
        self.groups[str(name)] = AccessSecurityGroup(
            context=context_from_lark_token(self.fn, asg_token),
            comments=self.get_recent_comments(asg_token.line),
            rules=rules,
            name=name,
            inputs=inputs,
        )

    asg_head = transformer.stringify
    asg_body = transformer.stringify
    asg_body_list = transformer.listify
    asg_body_item = transformer.pass_through

    def rule_config(self, rule_token: lark.Token, head, body=None):
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

    rule_body = transformer.pass_through
    rule_list = transformer.listify

    @staticmethod
    def rule_head(mandatory, options):
        level, log_options = mandatory
        return (level, log_options, options)

    @staticmethod
    def rule_head_mandatory(level, options):
        return (int(level), str(options))

    rule_head_options = transformer.pass_through
    rule_log_options = transformer.stringify

    rule_uag_list = transformer.listify_strings
    rule_hag_list = transformer.listify_strings

    def rule_uag(self, uag_token: lark.Token, users):
        self.rule_info[uag_token] = users

    def rule_hag(self, hag_token: lark.Token, hosts):
        self.rule_info[hag_token] = hosts

    def rule_calc(self, calc_token: lark.Token, calc_str):
        self.calc = (calc_token, str(calc_str).strip('" '))

    def inp_config(self, inp_token: lark.Token, link):
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

    def get_group_from_record(self, record: RecordInstance) -> Optional[AccessSecurityGroup]:
        """Get the appropriate access security group for the given record."""
        if record.is_pva:
            return

        return self.groups.get(record.access_security_group, None)

    @classmethod
    def from_string(cls, contents: str, filename: Optional[str] = None) -> AccessSecurityConfig:
        """
        Load access security configuration from a string.

        Parameters
        ----------
        contents : str
            The access security file contents.

        filename : str, optional
            The access security filename to use for LoadContext.
        """
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
    def from_file_obj(cls, fp, filename: Optional[str] = None) -> AccessSecurityConfig:
        """Load an ACF file from a file object."""
        filename = filename or getattr(fp, "name", str(id(fp)))
        return cls.from_string(fp.read(), filename=filename)

    @classmethod
    def from_file(cls, fn: Union[str, pathlib.Path]) -> AccessSecurityConfig:
        """Load an ACF file from a filename."""
        with open(fn, "rt") as fp:
            return cls.from_file_obj(fp, filename=str(fn))


_handler = ShellStateHandler.generic_handler_decorator


@dataclass
class AccessSecurityState(ShellStateHandler):
    """
    Access Security IOC shell state handler / container.

    Contains hooks for as-related commands and state information.

    Attributes
    ----------
    config : AccessSecurityState
        The access security configuration.
    filename : pathlib.Path
        The access security filename.
    macros : Dict[str, str]
        Macros used when expanding the access security file.
    """
    metadata_key: ClassVar[str] = "asg"
    config: Optional[AccessSecurityConfig] = None
    filename: Optional[pathlib.Path] = None
    macros: Optional[Dict[str, str]] = None

    def post_ioc_init(self):
        super().post_ioc_init()
        if self.filename is None:
            return

        try:
            return {
                "access_security": self._load_access_security()
            }
        except Exception as ex:
            return {
                "access_security": {
                    "exception_class": type(ex).__name__,
                    "error": str(ex),
                }
            }

    @_handler
    def handle_asSetSubstitutions(self, macros: str):
        if self.primary_handler is None:
            return

        macro_context = self.primary_handler.macro_context
        self.macros = macro_context.definitions_to_dict(macros)
        return {
            "macros": self.macros,
            "note": "See iocInit results for details.",
        }

    @_handler
    def handle_asSetFilename(self, filename: str):
        if self.primary_handler is None:
            return

        self.filename = self.primary_handler._fix_path(
            filename
        ).resolve()
        return {
            "filename": str(self.filename),
            "note": "See iocInit results for details.",
        }

    def _load_access_security(self):
        """Load access security settings at iocInit time."""
        if self.primary_handler is None:
            return

        filename, contents = self.primary_handler.load_file(self.filename)
        if self.macros:
            macro_context = MacroContext(use_environment=False)
            macro_context.define(**self.macros)
            contents = "\n".join(
                macro_context.expand(line)
                for line in contents.splitlines()
            )

        self.config = AccessSecurityConfig.from_string(
            contents, filename=str(filename)
        )
        return {
            "filename": filename,
            "macros": self.macros,
        }

    def annotate_record(self, record: RecordInstance) -> Optional[Dict[str, Any]]:
        """Annotate record with access security information."""
        if self.config is not None:
            asg = self.config.get_group_from_record(record)
            if asg is not None:
                return apischema.serialize(asg)
