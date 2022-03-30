import dataclasses
import textwrap
from typing import Optional, Set

import pytest

from .. import makefile


def prune_result(
    result: makefile.Makefile,
    expected: makefile.Makefile,
    to_keep: Optional[Set[str]] = None,
) -> None:
    """
    Prune resulting Makefile for the purposes of testing.

    * Remove extra environment variables that we don't want here
    """
    for key in set(result.env) - set(expected.env):
        result.env.pop(key)

    ignore = {"env", "filename"}
    for field in dataclasses.fields(makefile.Makefile):
        if field.name not in to_keep and field.name not in ignore:
            setattr(result, field.name, getattr(expected, field.name))


@pytest.mark.skipif(
    not makefile.host_has_make(),
    reason="Host does not have make"
)
@pytest.mark.parametrize(
    "contents, to_keep, expected",
    [
        pytest.param(
            """
            WHATREC_A=B
            WHATREC_C?=D
            """,
            set(),
            makefile.Makefile(
                env={"WHATREC_A": "B", "WHATREC_C": "D"},
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
            set(),
            makefile.Makefile(
                env={"WHATREC_A": "A", "WHATREC_B": "A", "WHATREC_C": "C"},
                filename=None,
            ),
            id="simple-subst",
        ),
        pytest.param(
            """
            ENV_VAR=A

            all:
                echo "Hi!"
            """,
            {"default_goal", },
            makefile.Makefile(
                env={"ENV_VAR": "A"},
                default_goal="all",
                filename=None,
            ),
            id="default-goal",
        ),
    ]
)
def test_from_contents(contents: str, expected: makefile.Makefile, to_keep: Set[str]):
    contents = textwrap.dedent(contents).replace("    ", "\t")
    result = makefile.Makefile.from_string(contents)
    prune_result(result, expected, to_keep=to_keep)
    assert result == expected
