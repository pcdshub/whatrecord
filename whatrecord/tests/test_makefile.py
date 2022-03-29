import textwrap

import pytest

from .. import makefile


def prune_result(
    info: makefile.MakefileInformation, expected: makefile.MakefileInformation
) -> None:
    """
    Prune resulting MakefileInformation for the purposes of testing.

    * Remove extra environment variables that we don't want here
    """
    for key in set(info.env) - set(expected.env):
        info.env.pop(key)


@pytest.mark.parametrize(
    "contents, expected",
    [
        pytest.param(
            """
            WHATREC_A=B
            WHATREC_C?=D
            """,
            makefile.MakefileInformation(
                env={"WHATREC_A": "B", "WHATREC_C": "D"},
                make_vars={"default_goal": ""},
                filename=None,
            ),
            id="simple-subst",
        ),
        pytest.param(
            """
            WHATREC_A=A
            WHATREC_B=$(WHATREC_A)
            WHATREC_C?=C
            """,
            makefile.MakefileInformation(
                env={"WHATREC_A": "A", "WHATREC_B": "A", "WHATREC_C": "C"},
                make_vars={"default_goal": ""},
                filename=None,
            ),
            id="simple-subst",
        ),
    ]
)
def test_from_contents(contents: str, expected: makefile.MakefileInformation):
    contents = textwrap.dedent(contents).replace("    ", "\t")
    result = makefile.MakefileInformation.from_makefile_contents(contents)
    prune_result(result, expected)
    assert result == expected
