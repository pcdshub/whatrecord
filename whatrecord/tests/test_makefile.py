import dataclasses
import pathlib
import subprocess
import textwrap
from typing import Optional, Set, Tuple

import pytest

from .. import makefile
from .conftest import MODULE_PATH, skip_without_make

DEPS_MAKEFILE_ROOT = MODULE_PATH / "deps"

# More coverage on debug log lines
makefile.logger.setLevel("DEBUG")


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


def get_makefile(contents: str, *, set_filename: bool = True) -> makefile.Makefile:
    """Get a Makefile instance given its contents."""
    contents = textwrap.dedent(contents).replace("    ", "\t")
    print("Creating Makefile from contents:")
    print(contents)
    make = makefile.Makefile.from_string(
        contents,
        filename=DEPS_MAKEFILE_ROOT / "Makefile.made_up" if set_filename else None,
    )
    if set_filename:
        # Make the object more realistic
        make.name = "ioc"
        make.variable_name = "ioc_var"
    return make


def get_dependency_group(
    contents: str, *, set_filename: bool = True
) -> Tuple[makefile.Makefile, makefile.DependencyGroup]:
    """Get a DependencyGroup instance given a single Makefile's contents."""
    root = get_makefile(contents, set_filename=set_filename)
    group = makefile.DependencyGroup.from_makefile(root)
    if set_filename:
        assert root.filename is not None
        assert group.root == root.filename.parent
    return root, group


def check_module_in_group(
    group: makefile.DependencyGroup, variable_name: str, path: pathlib.Path
) -> makefile.Dependency:
    """Check if a module is present in a DependencyGroup."""
    if path not in group.all_modules:
        paths = ", ".join(str(path) for path in group.all_modules)
        raise ValueError(
            f"Module {variable_name} not found in dependency list. "
            f"Paths: {paths}"
        )
    module = group.all_modules[path]
    assert module.variable_name == variable_name
    return module


@skip_without_make
def test_make_version():
    version = subprocess.check_output(["make", "--version"])
    print(version)


@skip_without_make
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
    result = get_makefile(contents, set_filename=False)
    print(result)
    prune_result(result, expected, to_keep=to_keep)
    assert result == expected


@skip_without_make
@pytest.mark.parametrize(
    "contents",
    [
        pytest.param(
            f"""
            EPICS_BASE={DEPS_MAKEFILE_ROOT}/base
            RELEASE_TOP=EPICS_BASE
            """,
            id="initial",
        ),
    ]
)
def test_dependency_norecurse_smoke(contents: str):
    make = get_makefile(contents)
    dep = makefile.Dependency.from_makefile(make, name="name", variable_name="var")
    assert dep.makefile == make
    assert dep.name == "name"
    assert dep.variable_name == "var"


@skip_without_make
def test_dependency_group_base_only():
    _, group = get_dependency_group(
        f"""
        EPICS_BASE={DEPS_MAKEFILE_ROOT}/base
        RELEASE_TOPS=EPICS_BASE
        """
    )

    assert len(group.all_modules) == 2

    base = check_module_in_group(group, "EPICS_BASE", DEPS_MAKEFILE_ROOT / "base")
    # I'm not convinced this is the right behavior, but not sure if we can
    # do better generically:
    assert base.name == "EPICS_BASE"


@skip_without_make
def test_dependency_group_base_and_module_a():
    _, group = get_dependency_group(
        f"""
        EPICS_BASE={DEPS_MAKEFILE_ROOT}/base
        MODULE_A={DEPS_MAKEFILE_ROOT}/module_a
        RELEASE_TOPS=EPICS_BASE MODULE_A
        """
    )

    assert len(group.all_modules) == 3
    check_module_in_group(group, "EPICS_BASE", DEPS_MAKEFILE_ROOT / "base")
    check_module_in_group(group, "MODULE_A", DEPS_MAKEFILE_ROOT / "module_a")


@skip_without_make
def test_dependency_group_base_and_layers():
    _, group = get_dependency_group(
        f"""
        EPICS_BASE={DEPS_MAKEFILE_ROOT}/base
        MODULE_C={DEPS_MAKEFILE_ROOT}/module_c
        RELEASE_TOPS=EPICS_BASE MODULE_C
        """
    )

    # test suite -> module_c   -> module_a -> base
    #         |                -> module_b -> base
    #         -> base
    #

    base = check_module_in_group(group, "EPICS_BASE", DEPS_MAKEFILE_ROOT / "base")
    ma = check_module_in_group(group, "MODULE_A", DEPS_MAKEFILE_ROOT / "module_a")
    mb = check_module_in_group(group, "MODULE_B", DEPS_MAKEFILE_ROOT / "module_b")
    mc = check_module_in_group(group, "MODULE_C", DEPS_MAKEFILE_ROOT / "module_c")
    ioc_path = DEPS_MAKEFILE_ROOT  # <-- test suite pseudo-makefile
    assert set(group.all_modules) == {
        ioc_path,
        base.path,
        ma.path,
        mb.path,
        mc.path,
    }
    assert len(group.all_modules) == 5

    # Base
    assert base.dependents == {
        "MODULE_A": ma.path,
        "MODULE_B": mb.path,
        "MODULE_C": mc.path,
        None: ioc_path,
    }
    assert len(base.dependencies) == 0

    # module a
    assert ma.dependencies == {"EPICS_BASE": base.path}
    assert ma.dependents == {"MODULE_C": mc.path}

    # module b
    assert mb.dependencies == {"EPICS_BASE": base.path}
    assert mb.dependents == {"MODULE_C": mc.path}

    # module c
    assert mc.dependencies == {
        "EPICS_BASE": base.path,
        "MODULE_A": ma.path,
        "MODULE_B": mb.path,
    }
    assert mc.dependents == {None: ioc_path}


@skip_without_make
def test_dependency_group_graph():
    _, group = get_dependency_group(
        f"""
        EPICS_BASE={DEPS_MAKEFILE_ROOT}/base
        MODULE_C={DEPS_MAKEFILE_ROOT}/module_c
        RELEASE_TOPS=EPICS_BASE MODULE_C
        """
    )
    graph = group.as_graph()
    assert len(graph.nodes) == 5

    base = check_module_in_group(group, "EPICS_BASE", DEPS_MAKEFILE_ROOT / "base")
    ma = check_module_in_group(group, "MODULE_A", DEPS_MAKEFILE_ROOT / "module_a")
    mb = check_module_in_group(group, "MODULE_B", DEPS_MAKEFILE_ROOT / "module_b")
    mc = check_module_in_group(group, "MODULE_C", DEPS_MAKEFILE_ROOT / "module_c")

    edge_pairs = list(graph.edge_pairs)

    def check_edge(source: makefile.Dependency, dest: makefile.Dependency):
        node_source = graph.get_node(str(source.path))
        node_dest = graph.get_node(str(dest.path))
        assert (node_source, node_dest) in edge_pairs

    check_edge(source=ma, dest=base)
    check_edge(source=mb, dest=base)
    check_edge(source=mc, dest=base)
    check_edge(source=mc, dest=ma)
    check_edge(source=mc, dest=mb)

    # Smoke test to_digraph
    graph.to_digraph()
