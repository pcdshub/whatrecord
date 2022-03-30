import dataclasses
import pathlib
import subprocess
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
def test_make_version():
    version = subprocess.check_output(["make", "--version"])
    print(version)
    raise


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
            id="simple-subst-0",
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
            id="simple-subst-1",
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
        pytest.param(
            # These would typically be set by the epics build system; but let's
            # set them ourselves as this is just a test of our stuff and not
            # the EPICS build system:
            """
            BUILD_ARCHS=arch1 arch2
            CROSS_COMPILER_HOST_ARCHS=arch3 arch4
            CROSS_COMPILER_TARGET_ARCHS=arch5 arch6
            BASE_MODULE_VERSION=R7.0.2
            CONFIG=/
            """,
            {
                "build_archs",
                "cross_compiler_host_archs",
                "cross_compiler_target_archs",
                "base_version",
                "base_config_path",
            },
            makefile.Makefile(
                env={},
                build_archs=["arch1", "arch2"],
                cross_compiler_host_archs=["arch3", "arch4"],
                cross_compiler_target_archs=["arch5", "arch6"],
                base_version="R7.0.2",
                base_config_path=pathlib.Path("/"),
                filename=None,
            ),
            id="epics-build-system-vars",
        ),
    ]
)
def test_from_contents(contents: str, expected: makefile.Makefile, to_keep: Set[str]):
    contents = textwrap.dedent(contents).replace("    ", "\t")
    result = makefile.Makefile.from_string(contents)
    print(result)
    prune_result(result, expected, to_keep=to_keep)
    assert result == expected
