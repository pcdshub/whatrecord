import pprint

import apischema
import pytest

from ..common import LoadContext
from ..dbtemplate import Substitution, TemplateSubstitution
from ..macro import MacroContext
from . import conftest

SUBSTITUTION_FILES = list((conftest.MODULE_PATH / "iocs").glob("**/*.substitutions"))

substitution_files = pytest.mark.parametrize(
    "substitution_file",
    [
        pytest.param(filename, id="/".join(filename.parts[-2:]))
        for filename in SUBSTITUTION_FILES
    ],
)


@substitution_files
def test_parse(substitution_file):
    sub = TemplateSubstitution.from_file(substitution_file)
    serialized = apischema.serialize(sub)
    pprint.pprint(serialized)
    apischema.deserialize(TemplateSubstitution, serialized)


epics_base_tests = [
    {
        "id": "epics-base-1",
        "result": """\
This is t1-template.txt

With $(a) & $(b):
"""
        + "This is t1-include.txt "
        + """
  a = default value used when a is undefined
  b = default value used when b is undefined
End of t1-include.txt

On defining a=aaa & b=bbb:
This is t1-include.txt again
  a = aaa
  b = bbb
End of t1-include.txt

On setting a="aa":
This is t1-include.txt again
  a = "aa"
  b = bbb
End of t1-include.txt

End of t1-template.txt
""",
        "include": """\
This is t1-include.txt $(include-file-again=)
  a = $(a=default value used when a is undefined)
  b = $(b=default value used when b is undefined)
substitute "include-file-again=again"
End of t1-include.txt
""",
        "template": """\
This is t1-template.txt

With $(a) & ${b}:
include "t1-include.txt"

substitute "a=aaa,b=bbb"
On defining a=$(a) & b=${b}:
include "t1-include.txt"

substitute "a=\"aa\""
On setting a=$(a):
include "t1-include.txt"

End of t1-template.txt
""",
    },
    {
        "id": "epics-base-2",
        "template": """\
a = $(a=def-a)  b = $(b=def-b)  c = $(c=def-c)  d = $(d,undef)
""",
        "substitution": """\
file t2-template.txt {
    {a=va1-a}
    {a=va2-a, b=va2-b}
    {a=va3-a, b=va3-b, c=va3-c}
    {a=va4-a, b=va4-b}
    {a=va5-a}
}
file t2-template.txt {
    pattern {a, b, c}
    {pt3-a, pt3-b, pt3-c}
}
""",
        "result": """\
a = va1-a  b = def-b  c = def-c  d = $(d)
a = va2-a  b = va2-b  c = def-c  d = $(d)
a = va3-a  b = va3-b  c = va3-c  d = $(d)
a = va4-a  b = va4-b  c = def-c  d = $(d)
a = va5-a  b = def-b  c = def-c  d = $(d)
a = pt3-a  b = pt3-b  c = pt3-c  d = $(d)
""",
    },
    {
        "id": "epics-base-3",
        "template": """\
a = $(a=def-a)  b = $(b=def-b)  c = $(c=def-c)  d = $(d,undef)
""",
        "substitution": """\
global {a=gb1-a, b=gb1-b}
file t3-template.txt {
    {}
    {a=va1-a}
    {a=va2-a, b=va2-b}
    {a=va3-a, b=va3-b, c=va3-c}
    {a=va4-a, b=va4-b}
    {a=va5-a}
    {}
    global {a=gb2-a, b=gb2-b}
    {}
    {a=va1-a}
    {a=va2-a, b=va2-b}
    {a=va3-a, b=va3-b, c=va3-c}
    {a=va4-a, b=va4-b}
    {a=va5-a}
    {}
}
global {b=gb3-b, a=gb3-a}
file t3-template.txt {
    pattern {a, b, c}
    {}
    {pt1-a}
    {pt2-a, pt2-b}
    {pt3-a, pt3-b, pt3-c}
    {pt4-a, pt4-b}
    {pt5-a}
    {}
    global {b=gb4-b, a=gb4-a}
    {}
    {pt1-a}
    {pt2-a, pt2-b}
    {pt3-a, pt3-b, pt3-c}
    {pt4-a, pt4-b}
    {pt5-a}
    {}
}
""",
        "result": """\
a = gb1-a  b = gb1-b  c = def-c  d = $(d)
a = va1-a  b = gb1-b  c = def-c  d = $(d)
a = va2-a  b = va2-b  c = def-c  d = $(d)
a = va3-a  b = va3-b  c = va3-c  d = $(d)
a = va4-a  b = va4-b  c = def-c  d = $(d)
a = va5-a  b = gb1-b  c = def-c  d = $(d)
a = gb1-a  b = gb1-b  c = def-c  d = $(d)
a = gb2-a  b = gb2-b  c = def-c  d = $(d)
a = va1-a  b = gb2-b  c = def-c  d = $(d)
a = va2-a  b = va2-b  c = def-c  d = $(d)
a = va3-a  b = va3-b  c = va3-c  d = $(d)
a = va4-a  b = va4-b  c = def-c  d = $(d)
a = va5-a  b = gb2-b  c = def-c  d = $(d)
a = gb2-a  b = gb2-b  c = def-c  d = $(d)
a = gb3-a  b = gb3-b  c = def-c  d = $(d)
a = pt1-a  b = gb3-b  c = def-c  d = $(d)
a = pt2-a  b = pt2-b  c = def-c  d = $(d)
a = pt3-a  b = pt3-b  c = pt3-c  d = $(d)
a = pt4-a  b = pt4-b  c = def-c  d = $(d)
a = pt5-a  b = gb3-b  c = def-c  d = $(d)
a = gb3-a  b = gb3-b  c = def-c  d = $(d)
a = gb4-a  b = gb4-b  c = def-c  d = $(d)
a = pt1-a  b = gb4-b  c = def-c  d = $(d)
a = pt2-a  b = pt2-b  c = def-c  d = $(d)
a = pt3-a  b = pt3-b  c = pt3-c  d = $(d)
a = pt4-a  b = pt4-b  c = def-c  d = $(d)
a = pt5-a  b = gb4-b  c = def-c  d = $(d)
a = gb4-a  b = gb4-b  c = def-c  d = $(d)
""",
    },
    {
        "id": "epics-base-4",
        "global": True,  # msi -g
        "result": """\
a = va1-a  b = def-b  c = def-c  d = $(d)
a = va2-a  b = va2-b  c = def-c  d = $(d)
a = va3-a  b = va3-b  c = va3-c  d = $(d)
a = va4-a  b = va4-b  c = va3-c  d = $(d)
a = va5-a  b = va4-b  c = va3-c  d = $(d)
a = pt3-a  b = pt3-b  c = pt3-c  d = $(d)
""",
        "substitution": """\
file t2-template.txt {
    {a=va1-a}
    {a=va2-a, b=va2-b}
    {a=va3-a, b=va3-b, c=va3-c}
    {a=va4-a, b=va4-b}
    {a=va5-a}
}
file t2-template.txt {
    pattern {a, b, c}
    {pt3-a, pt3-b, pt3-c}
}
""",
        "template": """\
a = $(a=def-a)  b = $(b=def-b)  c = $(c=def-c)  d = $(d,undef)
""",
    },
    {
        "id": "epics-base-5",
        "result": """\
# comment line
a = 111
b = 222
c = xx
d = $(d)
# comment line
a = aaa
b = bbb
c = ccc
d = $(d)
# comment line
a = AA
b = BB
c = xx
d = $(d)
# comment line
a = aaa
b = bbb
c = yy
d = $(d)
""",
        "template": """\
# comment line
a = $(a)
b = $(b)
c = $(c)
d = $(d)
""",
        "substitution": """\
global {c=xx}
{a=111,b="222"}
{ 	a 	= 	aaa   ,   b=bbb , c = ccc}
{a=AA,b='BB'}
global { c = yy }
{
    a=	 aaa
    b=	 bbb
}
""",
    },
    {
        "id": "epics-base-6",
        "substitution": """\
global {c=xx}
pattern {b,a}
{"222",111}
pattern {a b c}
{ 	aaa   ,   bbb , ccc}
pattern { a , b }
{AA,'BB'}
global { c = yy }
pattern { a , b }
{
	 aaa
	 bbb
}
""",  # noqa: W191 E101
        "template": """\
# comment line
a = $(a)
b = $(b)
c = $(c)
d = $(d)
""",
        "result": """\
# comment line
a = 111
b = 222
c = xx
d = $(d)
# comment line
a = aaa
b = bbb
c = ccc
d = $(d)
# comment line
a = AA
b = BB
c = xx
d = $(d)
# comment line
a = aaa
b = bbb
c = yy
d = $(d)
""",
    },
    #     {
    #         "id": "epics-base-7",
    #         "result": """\
    # This is t1-template.txt
    #
    # With $(a,undefined) & $(b,undefined):
    # This is t1-include.txt
    #   a = default value used when a is undefined
    #   b = default value used when b is undefined
    # End of t1-include.txt
    #
    # On defining a=aaa & b=bbb:
    # This is t1-include.txt again
    #   a = aaa
    #   b = bbb
    # End of t1-include.txt
    #
    # On setting a="aa":
    # This is t1-include.txt again
    #   a = "aa"
    #   b = bbb
    # End of t1-include.txt
    #
    # End of t1-template.txt
    # """,
    #     },
    #    {
    #        "id": "epics-base-8",
    #        "result": """\
    # t8.txt: ../t1-template.txt \
    # ../t1-include.txt
    # """,
    #    },
    #    {
    #        "id": "epics-base-9",
    #        "result": """\
    # t9.txt: ../t2-template.txt
    # """,
    #    },
    {
        "id": "epics-base-10",
        "substitution": """\
file t10-template.txt {
    {}
}

global { a=gbl }
file t10-template.txt {
    {}
}
""",
        "result": """\
# comment line
a=$(a)
# comment line
a=gbl
""",
        "template": """\
# comment line
a=$(a)
""",
    },
    {
        "id": "epics-base-11",
        "substitution": """\
file t11-template.txt {
    pattern {}
    {}
}

global { a=gbl }
file t11-template.txt {
    pattern {}
    {}
}
""",
        "result": """\
# comment line
a=$(a)
# comment line
a=gbl
""",
        "template": """\
# comment line
a=$(a)
""",
    },
    {
        "id": "epics-base-12",
        "template": """\
# comment line
a=$(a)
""",
        "result": """\
# comment line
a=foo
""",
        "substitution": """\
file $(PREFIX)$(TEST_NO)-template.txt {
    { a=foo }
}
""",
        "macros": {"TEST_NO": 12, "PREFIX": "t"},
    },
]


@pytest.mark.parametrize(
    "substitution, template, include, macros, expected, all_global",
    [
        pytest.param(
            test.get("substitution"),
            test.get("template"),
            test.get("include"),
            test.get("macros"),
            test.get("result"),
            test.get("global", False),
            id=test["id"],
        )
        for test in epics_base_tests
    ],
)
def test_msi_base_examples(
    substitution, template, include, macros, expected, all_global
):
    macros = macros or {}

    if substitution:
        macro_ctx = MacroContext()
        macro_ctx.define(**macros)
        sub = TemplateSubstitution.from_string(
            macro_ctx.expand(substitution),
            msi_format=True,
            filename="test.substitutions",
            all_global_scope=all_global,
        )
        result = []
        for single_sub in sub.substitutions:
            result.extend(single_sub.expand(template).splitlines())

        result = "\n".join(line for line in result if line.strip())
        expected = "\n".join(line for line in expected.splitlines() if line.strip())
        print("result")
        print("------")
        print(result)
        print("------")
        print("expected")
        print("------")
        print(expected)
        print("------")
        assert result == expected

    elif template:
        sub = Substitution(
            context=[LoadContext("None", 1)],
            filename=None,
            macros=macros,
        )
        result = sub.expand(template, search_paths=[conftest.MODULE_PATH])
        print("macros", macros)
        print("result")
        print("------")
        print(result)
        print("------")
        print("expected")
        print("------")
        print(expected)
        print("------")
        assert result.strip() == expected.strip()
    else:
        raise ValueError("Invalid test params?")

    serialized = apischema.serialize(sub)
    pprint.pprint(serialized)
    apischema.deserialize(type(sub), serialized)
