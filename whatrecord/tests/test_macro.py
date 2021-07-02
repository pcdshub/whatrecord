import os

import pytest

from .. import MacroContext


def test_env():
    os.environ["C"] = "3"
    os.environ["D"] = "4"
    os.environ["E"] = "5"

    ctx = MacroContext(use_environment=True)
    ctx.define_from_string("A=1,B=2,E=15")

    assert ctx["A"] == "1"
    assert ctx["B"] == "2"
    assert ctx["C"] == "3"
    assert ctx["D"] == "4"
    assert ctx["E"] == "15"

    assert set(list(ctx.items())[-6:]) == {
        ("A", "1"),
        ("B", "2"),
        ("C", "3"),
        ("D", "4"),
        ("E", "15"),
    }
    with pytest.raises(KeyError):
        ctx["F"]

    with ctx.scoped(**ctx.definitions_to_dict("A=11,C=13,D=14,G=7")):
        assert ctx["A"] == "11"
        assert ctx["B"] == "2"
        assert ctx["C"] == "13"
        assert ctx["D"] == "14"
        assert ctx["E"] == "15"
        with pytest.raises(KeyError):
            ctx["F"]
        assert ctx["G"] == "7"

        # implicit when called through in iocshBody
        os.environ["D"] = "24"
        ctx["D"] = "24"
        os.environ["F"] = "6"
        ctx["F"] = "6"
        os.environ["G"] = "17"
        ctx["G"] = "17"

        assert ctx["D"] == "24"
        assert ctx["F"] == "6"
        assert ctx["G"] == "17"

    assert ctx["A"] == "1"
    assert ctx["B"] == "2"
    assert ctx["C"] == "3"
    assert ctx["D"] == "24"
    assert ctx["E"] == "15"
    assert ctx["F"] == "6"
    assert ctx["G"] == "17"

    with ctx.scoped(**ctx.definitions_to_dict("D=34,G=27")):
        assert ctx["D"] == "34"
        assert ctx["G"] == "27"

    assert ctx["D"] == "24"


def test_empty():
    ctx = MacroContext(use_environment=False)
    with pytest.raises(KeyError):
        ctx["A"]
    with pytest.raises(KeyError):
        ctx["HOSTNAME"]


def test_misc_with_env():
    def check(macro_string, macros, expected):
        ctx = MacroContext(use_environment=True)
        ctx.define_from_string(macros)
        expanded = ctx.expand(macro_string, empty_on_failure=True)
        print(f"{macro_string!r} expanded to {expanded!r} with {macros!r}")
        assert expanded == expected

    os.environ.pop("FOO", None)
    check("FOO", "", "FOO")

    # NOTE: a bit of an API break here, we always want a string from expand,
    # but the original would return NULL (could be Python None)
    check("${FOO}", "", "")
    check("${FOO,BAR}", "", "")
    check("${FOO,BAR=baz}", "", "")
    check("${FOO,BAR=$(FOO)}", "", "")
    check("${FOO,FOO}", "", "")
    check("${FOO,FOO=$(FOO)}", "", "")
    check("${FOO,BAR=baz,FUM}", "", "")

    check("${=}", "", "")
    check("x${=}y", "", "xy")

    check("${,=}", "", "")
    check("x${,=}y", "", "xy")

    check("${FOO=}", "", "")
    check("x${FOO=}y", "", "xy")

    check("${FOO=,}", "", "")
    check("x${FOO=,}y", "", "xy")

    check("${FOO,FOO=}", "", "")
    check("x${FOO,FOO=}y", "", "xy")

    check("${FOO=,BAR}", "", "")
    check("x${FOO=,BAR}y", "", "xy")

    check("${FOO=$(BAR=)}", "", "")
    check("x${FOO=$(BAR=)}y", "", "xy")

    check("${FOO=,BAR=baz}", "", "")
    check("x${FOO=,BAR=baz}y", "", "xy")

    check("${FOO=$(BAR),BAR=}", "", "")
    check("x${FOO=$(BAR),BAR=}y", "", "xy")

    check("${=BAR}", "", "BAR")
    check("x${=BAR}y", "", "xBARy")

    check("${FOO=BAR}", "", "BAR")
    check("x${FOO=BAR}y", "", "xBARy")

    os.environ["FOO"] = "BLETCH"
    check("${FOO}", "", "BLETCH")
    check("${FOO,FOO}", "", "BLETCH")
    check("x${FOO}y", "", "xBLETCHy")
    check("x${FOO}y${FOO}z", "", "xBLETCHyBLETCHz")
    check("${FOO=BAR}", "", "BLETCH")
    check("x${FOO=BAR}y", "", "xBLETCHy")
    check("${FOO=${BAZ}}", "", "BLETCH")
    check("${FOO=${BAZ},BAR=$(BAZ)}", "", "BLETCH")
    check("x${FOO=${BAZ}}y", "", "xBLETCHy")
    check("x${FOO=${BAZ},BAR=$(BAZ)}y", "", "xBLETCHy")
    check("${BAR=${FOO}}", "", "BLETCH")
    check("x${BAR=${FOO}}y", "", "xBLETCHy")
    check("w${BAR=x${FOO}y}z", "", "wxBLETCHyz")

    check("${FOO,FOO=BAR}", "", "BAR")
    check("x${FOO,FOO=BAR}y", "", "xBARy")
    check("${BAR,BAR=$(FOO)}", "", "BLETCH")
    check("x${BAR,BAR=$(FOO)}y", "", "xBLETCHy")
    check("${BAR,BAR=$($(FOO)),BLETCH=GRIBBLE}", "", "GRIBBLE")
    check("x${BAR,BAR=$($(FOO)),BLETCH=GRIBBLE}y", "", "xGRIBBLEy")
    check("${$(BAR,BAR=$(FOO)),BLETCH=GRIBBLE}", "", "GRIBBLE")
    check("x${$(BAR,BAR=$(FOO)),BLETCH=GRIBBLE}y", "", "xGRIBBLEy")

    check("${FOO}/${BAR}", "BAR=GLEEP", "BLETCH/GLEEP")
    check("x${FOO}/${BAR}y", "BAR=GLEEP", "xBLETCH/GLEEPy")
    check("${FOO,BAR}/${BAR}", "BAR=GLEEP", "BLETCH/GLEEP")
    check("${FOO,BAR=x}/${BAR}", "BAR=GLEEP", "BLETCH/GLEEP")
    check("${BAZ=BLETCH,BAR}/${BAR}", "BAR=GLEEP", "BLETCH/GLEEP")
    check("${BAZ=BLETCH,BAR=x}/${BAR}", "BAR=GLEEP", "BLETCH/GLEEP")

    check("${${FOO}}", "BAR=GLEEP,BLETCH=BAR", "BAR")
    check("x${${FOO}}y", "BAR=GLEEP,BLETCH=BAR", "xBARy")
    check("${${FOO}=GRIBBLE}", "BAR=GLEEP,BLETCH=BAR", "BAR")
    check("x${${FOO}=GRIBBLE}y", "BAR=GLEEP,BLETCH=BAR", "xBARy")

    check("${${FOO}}", "BAR=GLEEP,BLETCH=${BAR}", "GLEEP")

    os.environ["FOO"] = "${BAR}"
    check("${FOO}", "BAR=GLEEP,BLETCH=${BAR}", "GLEEP")

    # NOTE: None case
    check("${FOO}", "BAR=${BAZ},BLETCH=${BAR}", "")

    check("${FOO}", "BAR=${BAZ=GRIBBLE},BLETCH=${BAR}", "GRIBBLE")

    check("${FOO}", "BAR=${STR1},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "VAL1")

    check("${FOO}", "BAR=${STR2},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "VAL2")

    # NOTE: None cases
    check("${FOO}", "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "")
    check("${FOO,FOO=$(FOO)}", "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "")
    check("${FOO=$(FOO)}", "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "")
    check("${FOO=$(BAR),BAR=$(FOO)}", "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "")
    os.environ.pop("FOO", None)


def test_not_empty_on_failure():
    def check(macro_string, macros, expected):
        ctx = MacroContext(use_environment=True)
        ctx.define_from_string(macros)
        expanded = ctx.expand(macro_string, empty_on_failure=False)
        print(f"{macro_string!r} expanded to {expanded!r} with {macros!r}")
        if expected:
            assert expanded == expected

    os.environ.pop("FOO", None)
    check("${FOO}", "", "$(FOO)")
    check("${FOO,BAR}", "", "$(FOO)")
    check("${FOO,BAR=baz}", "", "$(FOO)")
    check("${FOO,BAR=$(FOO)}", "", "$(FOO)")
    check("${FOO,FOO}", "", "$(FOO)")
    check("${FOO,FOO=$(FOO)}", "", "$(FOO)")
    check("${FOO,BAR=baz,FUM}", "", "$(FOO)")

    os.environ["FOO"] = "${BAR}"
    check("${FOO}", "BAR=${BAZ},BLETCH=${BAR}", "$(BAZ)")
    check("${FOO}", "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "$(BAR)")
    check("${FOO,FOO=$(FOO)}", "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "$(FOO)")
    check("${FOO=$(FOO)}", "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "$(BAR)")
    check("${FOO=$(BAR),BAR=$(FOO)}", "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "$(BAR)")

    os.environ.pop("FOO", None)


def test_not_empty_on_failure_show_warnings():
    def check(macro_string, macros, expected):
        ctx = MacroContext(use_environment=True, show_warnings=True)
        ctx.define_from_string(macros)
        expanded = ctx.expand(macro_string, empty_on_failure=False)
        print(f"{macro_string!r} expanded to {expanded!r} with {macros!r}")
        if expected:
            assert expanded == expected

    os.environ.pop("FOO", None)
    check("${FOO}", "", "$(FOO,undefined)")
    check("${FOO,BAR}", "", "$(FOO,undefined)")
    check("${FOO,BAR=baz}", "", "$(FOO,undefined)")
    check("${FOO,BAR=$(FOO)}", "", "$(FOO,undefined)")
    check("${FOO,FOO}", "", "$(FOO,undefined)")
    check("${FOO,FOO=$(FOO)}", "", "$(FOO,recursive)")
    check("${FOO,BAR=baz,FUM}", "", "$(FOO,undefined)")

    os.environ["FOO"] = "${BAR}"
    check("${FOO}", "BAR=${BAZ},BLETCH=${BAR}", "$(BAZ,undefined)")
    check("${FOO}", "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2", "$(BAR,recursive)")
    check(
        "${FOO,FOO=$(FOO)}",
        "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2",
        "$(FOO,recursive)",
    )
    check(
        "${FOO=$(FOO)}",
        "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2",
        "$(BAR,recursive)",
    )
    check(
        "${FOO=$(BAR),BAR=$(FOO)}",
        "BAR=${FOO},BLETCH=${BAR},STR1=VAL1,STR2=VAL2",
        "$(BAR,recursive)",
    )

    os.environ.pop("FOO", None)


def test_python_niceties():
    ctx = MacroContext(use_environment=False)
    ctx["B"] = "5"
    with pytest.raises(KeyError):
        ctx["A"]
    assert ctx["B"] == "5"

    ctx.define(C="6")
    assert ctx["C"] == "6"

    assert ctx.items()
    assert set(list(ctx.items())) == {
        ("B", "5"),
        ("C", "6"),
    }

    assert set(ctx) == {"B", "C"}
