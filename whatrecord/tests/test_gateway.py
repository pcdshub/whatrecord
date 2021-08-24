import pytest

from .. import util
from ..common import LoadContext
from ..gateway import (AccessSecurity, AliasRule, AllowRule, DenyRule,
                       GatewayConfig, PVList, PVListMatch, PVListMatches)
from .conftest import MODULE_PATH


@pytest.fixture
def kfe_pvlist():
    return PVList.from_file(
        (MODULE_PATH / "kfe.pvlist").resolve()
    )


@pytest.fixture
def gateway_config():
    return GatewayConfig(path=MODULE_PATH, glob_str="*.pvlist")


@pytest.mark.parametrize(
    "rule, expected",
    [
        pytest.param(
            "SXR:YAG:CVV:01.* ALLOW RWINSTRMCC 1",
            AllowRule(
                context=(LoadContext("None", 1), ),
                command="ALLOW",
                pattern="SXR:YAG:CVV:01.*",
                access=AccessSecurity(
                    group="RWINSTRMCC",
                    level="1",
                )
            ),
            id="allow_basic",
        ),
        pytest.param(
            "SXR:YAG:CVV:01.* DENY",
            DenyRule(
                context=(LoadContext("None", 1), ),
                command="DENY",
                pattern="SXR:YAG:CVV:01.*",
                hosts=[],
            ),
            id="deny_basic",
        ),
        pytest.param(
            "SXR:YAG:CVV:01.* DENY FROM host1",
            DenyRule(
                context=(LoadContext("None", 1), ),
                command="DENY",
                pattern="SXR:YAG:CVV:01.*",
                hosts=["host1"],
            ),
            id="deny_host",
        ),
        pytest.param(
            "SXR:YAG:CVV:01.* DENY FROM host1 host2",
            DenyRule(
                context=(LoadContext("None", 1), ),
                command="DENY",
                pattern="SXR:YAG:CVV:01.*",
                hosts=["host1", "host2"],
            ),
            id="deny_hosts",
        ),
        pytest.param(
            r":gateway\.\(.*\)Flag        ALIAS     gateway:\1Flag       ",
            AliasRule(
                context=(LoadContext("None", 1), ),
                command="ALIAS",
                pattern=r":gateway\.\(.*\)Flag",
                pvname=r"gateway:\1Flag",
                access=None,
            ),
            id="alias",
        ),
        pytest.param(
            r":gateway\.\(.*\)Flag        ALIAS     gateway:\1Flag          GatewayAdmin",
            AliasRule(
                context=(LoadContext("None", 1), ),
                command="ALIAS",
                pattern=r":gateway\.\(.*\)Flag",
                pvname=r"gateway:\1Flag",
                access=AccessSecurity(
                    group="GatewayAdmin",
                    level=None,
                )
            ),
            id="alias_access",
        ),

        pytest.param(
            "*        ALIAS     gateway:Flag",
            AliasRule(
                context=(LoadContext("None", 1), ),
                command="ALIAS",
                pattern="*",
                pvname="gateway:Flag",
                # Hard to test for, as this is set automatically:
                # metadata={
                #     "error": (
                #         "Invalid regex. error: nothing to "
                #         "repeat at position 0'",
                #     )
                # }
            ),
            id="invalid_pattern",
        ),

    ]
)
def test_rule(rule, expected):
    assert PVList.from_string(rule).rules[0] == expected


def test_eval_order():
    assert PVList.from_string(
        "evaluation order allow, deny"
    ).evaluation_order == "ALLOW, DENY"


def test_full():
    source = """
        # Header Text 1
        # Header Text 2
        evaluation order allow, deny

        # Skipped Comment

        # Rule Comment 1
        # Rule Comment 2
        SXR:YAG:CVV:01.* ALLOW RWINSTRMCC 1
    """

    source_hash = util.get_bytes_sha256(source.encode("utf-8"))
    assert PVList.from_string(
        source,
        filename="filename",
    ) == PVList(
        filename="filename",
        evaluation_order="ALLOW, DENY",
        comments=[
            "Header Text 1",
            "Header Text 2",
            "Skipped Comment",
            "Rule Comment 1",
            "Rule Comment 2",
        ],
        header="Header Text 1\nHeader Text 2",
        hash=source_hash,
        rules=[
            AllowRule(
                context=(LoadContext("filename", 9), ),
                command="ALLOW",
                pattern="SXR:YAG:CVV:01.*",
                access=AccessSecurity(
                    group="RWINSTRMCC",
                    level="1",
                ),
                header="Rule Comment 1\nRule Comment 2",
            ),
        ],
    )


def test_match_without_context(kfe_pvlist: PVList):
    assert list(kfe_pvlist.match("IOC:KFE:ABC")) == [
        (
            AllowRule(
                context=(LoadContext(kfe_pvlist.filename, 10,), ),
                pattern="[A-Z][A-Z][A-Z]:KFE:.*",
                command="ALLOW",
                # regex=re.compile("[A-Z][A-Z][A-Z]:KFE:.*"),
                header="",
                metadata={},
                access=None,
            ),
            []
        )
    ]


def test_match_with_context(kfe_pvlist: PVList):
    assert list(kfe_pvlist.match("IOC:RIX:ABC")) == [
        (
            AllowRule(
                context=(LoadContext(kfe_pvlist.filename, 13,), ),
                pattern="[A-Z][A-Z][A-Z]:RIX:.*",
                command="ALLOW",
                # regex=re.compile("[A-Z][A-Z][A-Z]:KFE:.*"),
                header="Some RIX devices temporarily on KFE subnet",
                metadata={},
                access=None,
            ),
            []
        )
    ]


def test_gateway_config(kfe_pvlist: PVList, gateway_config: GatewayConfig):
    gateway_config.update_changed()

    kfe_fn = str(kfe_pvlist.filename)
    assert gateway_config.get_matches("IOC:RIX:ABC") == PVListMatches(
        name="IOC:RIX:ABC",
        matches=[
            PVListMatch(
                filename=kfe_fn,
                rule=AllowRule(
                    context=(LoadContext(kfe_fn, 13,), ),
                    pattern="[A-Z][A-Z][A-Z]:RIX:.*",
                    command="ALLOW",
                    # regex=re.compile("[A-Z][A-Z][A-Z]:KFE:.*"),
                    header="Some RIX devices temporarily on KFE subnet",
                    metadata={},
                    access=None,
                ),
                groups=[],
            ),
        ]
    )
