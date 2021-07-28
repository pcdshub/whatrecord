import pytest

from ..access_security import (AccessSecurityConfig, AccessSecurityGroup,
                               AccessSecurityRule, HostAccessGroup,
                               UserAccessGroup)
from ..common import LoadContext
from .conftest import MODULE_PATH

ACF_FILES = MODULE_PATH.glob("*.acf")

acf_files = pytest.mark.parametrize(
    "acf_file",
    [
        pytest.param(
            acf_file,
            id=acf_file.name,
        )
        for acf_file in ACF_FILES
    ]
)


def test_hag_simple():
    acf = AccessSecurityConfig.from_string("HAG(group) {host1, host2, host3}")
    assert acf.hosts["group"] == HostAccessGroup(
        context=(LoadContext("None", 1),),
        name="group",
        comments="",
        hosts=["host1", "host2", "host3"],
    )


def test_hag_simple_comments():
    acf = AccessSecurityConfig.from_string("""
# My group
# Information
HAG(group) {host1, host2, host3}
""")
    assert acf.hosts["group"] == HostAccessGroup(
        context=(LoadContext("None", 4),),
        name="group",
        comments="My group\nInformation",
        hosts=["host1", "host2", "host3"],
    )


def test_uag_simple():
    acf = AccessSecurityConfig.from_string(
        """
UAG(op) {op1,op2,superguy}
UAG(opSup) {superguy}
        """
    )

    assert acf.users["op"] == UserAccessGroup(
        context=(LoadContext("None", 2),),
        name="op",
        comments="",
        users=["op1", "op2", "superguy"],
    )

    assert acf.users["opSup"] == UserAccessGroup(
        context=(LoadContext("None", 3),),
        name="opSup",
        comments="",
        users=["superguy"],
    )


def test_uag_simple_comments():
    acf = AccessSecurityConfig.from_string(
        """
# Comments 1
UAG(op) {op1,op2,superguy}
# Comments 2
UAG(opSup) {superguy}
        """
    )

    assert acf.users["op"] == UserAccessGroup(
        context=(LoadContext("None", 3),),
        name="op",
        comments="Comments 1",
        users=["op1", "op2", "superguy"],
    )

    assert acf.users["opSup"] == UserAccessGroup(
        context=(LoadContext("None", 5),),
        name="opSup",
        comments="Comments 2",
        users=["superguy"],
    )


def test_asg_simple():
    acf = AccessSecurityConfig.from_string(
        """
    ASG(permit) {
        RULE(0,WRITE) {
            UAG(opSup,linacSup,appDev)
            HAG(host1, host2)
        }
        RULE(1,READ)
        RULE(1,WRITE) {
            HAG(ioc)
        }
    }
    """
    )

    assert acf.groups["permit"] == AccessSecurityGroup(
        context=(LoadContext("None", 2),),
        name="permit",
        comments="",
        rules=[
            AccessSecurityRule(
                context=(LoadContext("None", 3),),
                level=0,
                options="WRITE",
                comments="",
                log_options=None,
                users=["opSup", "linacSup", "appDev"],
                hosts=["host1", "host2"],
            ),
            AccessSecurityRule(
                context=(LoadContext("None", 7),),
                level=1,
                options="READ",
                comments="",
                log_options=None,
            ),
            AccessSecurityRule(
                context=(LoadContext("None", 8),),
                level=1,
                options="WRITE",
                comments="",
                log_options=None,
                hosts=["ioc"],
            ),
        ],
    )


def test_asg_log_options():
    acf = AccessSecurityConfig.from_string(
        """
# Comments
ASG(RWINSTRMCC) {
    # Comments 2
    RULE(1,WRITE,TRAPWRITE){
      HAG(drphosts,xpphosts)
    }
}
    """
    )

    assert acf.groups["RWINSTRMCC"] == AccessSecurityGroup(
        context=(LoadContext("None", 3),),
        name="RWINSTRMCC",
        comments="Comments",
        rules=[
            AccessSecurityRule(
                context=(LoadContext("None", 5),),
                level=1,
                options="WRITE",
                comments="Comments 2",
                log_options="TRAPWRITE",
                hosts=["drphosts", "xpphosts"],
            ),
        ],
    )


def test_asg_calc():
    acf = AccessSecurityConfig.from_string(
        """
ASG(DEFAULT) {
    INPA(LI:OPSTATE)
    INPB(LI:lev1permit)
    RULE(0,WRITE) {
        UAG(op)
        HAG(icr,cr)
        CALC("A=1")
    }
    RULE(0,WRITE) {
        UAG(op,linac,appdev)
        HAG(icr,cr)
        CALC("A=0")
    }
    RULE(1,WRITE) {
        UAG(opSup,linacSup,appdev)
        CALC("B=1")
    }
    RULE(1,READ)
    RULE(1,WRITE) {
        HAG(ioc)
    }
}
    """
    )

    assert acf.groups["DEFAULT"] == AccessSecurityGroup(
        context=(LoadContext("None", 2),),
        name="DEFAULT",
        comments="",
        inputs={"INPA": "LI:OPSTATE", "INPB": "LI:lev1permit"},
        rules=[
            AccessSecurityRule(
                context=(LoadContext("None", 5),),
                level=0,
                options="WRITE",
                log_options=None,
                users=["op"],
                hosts=["icr", "cr"],
                calc="A=1",
                comments="",
            ),
            AccessSecurityRule(
                context=(LoadContext("None", 10),),
                level=0,
                options="WRITE",
                log_options=None,
                users=["op", "linac", "appdev"],
                hosts=["icr", "cr"],
                calc="A=0",
                comments="",
            ),
            AccessSecurityRule(
                context=(LoadContext("None", 15),),
                level=1,
                options="WRITE",
                log_options=None,
                users=["opSup", "linacSup", "appdev"],
                calc="B=1",
                comments="",
            ),
            AccessSecurityRule(
                context=(LoadContext("None", 19),),
                level=1,
                options="READ",
                comments="",
            ),
            AccessSecurityRule(
                context=(LoadContext("None", 20),),
                level=1,
                options="WRITE",
                hosts=["ioc"],
                comments="",
            ),
        ],
    )


@acf_files
def test_load_full_acf_file_smoke(acf_file):
    loaded = AccessSecurityConfig.from_file(acf_file)
    # This is a smoke test - take a look at the output if interested
    print(loaded)
    assert loaded is not None
