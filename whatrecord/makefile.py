from __future__ import annotations

import functools
import logging
import os
import pathlib
import shutil
import subprocess
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Union

import apischema
import graphviz as gv

from .common import AnyPath
from .graph import _GraphHelper
from .util import lines_between

logger = logging.getLogger(__name__)


class MakeNotInstalled(RuntimeError):
    ...


_section_start_marker = "--whatrecord-section-start--"
_section_end_marker = "--whatrecord-section-end--"
_whatrecord_target = "_whatrecord_target"

_make_helper: str = fr"""

# Trick borrowed from epics-sumo; thanks!
.EXPORT_ALL_VARIABLES:
# per GNU Make's documentation:
#   Simply by being mentioned as a target, this
#   tells make to export all variables to child processes by default. See
#   Communicating Variables to a Sub-make.

{_whatrecord_target}:
    # This is the environment section; null-delimited list of env vars
    @echo "{_section_start_marker}env"
    @env -0
    @echo "{_section_end_marker}"
    # This is the make meta information section, as specified by make itself
    @echo "{_section_start_marker}default_goal"
    @echo "$(.DEFAULT_GOAL)"
    @echo "{_section_end_marker}"
    @echo "{_section_start_marker}makefile_list"
    @echo "$(MAKEFILE_LIST)"
    @echo "{_section_end_marker}"
    @echo "{_section_start_marker}make_features"
    @echo "$(.FEATURES)"
    @echo "{_section_start_marker}include_dirs"
    @echo "$(.INCLUDE_DIRS)"
    @echo "{_section_end_marker}"
""".replace("    ", "\t")


@functools.lru_cache(maxsize=None)
def host_has_make() -> bool:
    """Does the host have ``make`` required to use this module?"""
    return shutil.which("make") is not None


@dataclass
class Makefile:
    """
    Makefile information as determined by ``make`` itself.

    Makes some assumptions about variables typically used in EPICS build
    environments, but should fill in generic information for all non-EPICS
    makefiles as well.

    Will not work if:
    * ``.RECIPEPREFIX`` is set to anything but tab in the makefile, however
        uncommon that may be.
    """

    #: Environment variable name to value.
    env: Dict[str, str] = field(default_factory=dict)
    #: .DEFAULT_GOAL, or the default ``make`` target.
    default_goal: str = ""
    #: .MAKEFILE_LIST, or the makefiles included in the build.
    makefile_list: List[str] = field(default_factory=list)
    #: .FEATURES, features supported by make
    make_features: Set[str] = field(default_factory=set)
    #: .INCLUDE_DIRS, include directories
    include_dirs: List[str] = field(default_factory=list)
    #: BUILD_ARCHS
    build_archs: List[str] = field(default_factory=list)
    #: CROSS_COMPILER_HOST_ARCHS
    cross_compiler_host_archs: List[str] = field(default_factory=list)
    #: CROSS_COMPILER_TARGET_ARCHS
    cross_compiler_target_archs: List[str] = field(default_factory=list)
    #: epics-base version.
    base_version: Optional[str] = None
    #: epics-base configure path.
    base_config_path: Optional[pathlib.Path] = None
    #: Variables defined in RELEASE_TOP
    release_top_vars: List[str] = field(default_factory=list)
    #: The Makefile filename, if available.
    filename: Optional[pathlib.Path] = None

    def find_release_paths(self, check: bool = True) -> Dict[str, pathlib.Path]:
        """
        Find paths defined in RELEASE.

        Parameters
        ----------
        check : bool, optional
            Check that the release path includes a ``configure`` directory and
            a ``Makefile``.
        """
        # TODO: are the checks here appropriate? Perhaps just a simple
        # ``path/Makefile`` check is sufficient for the build system.
        results = {}
        for var in self.release_top_vars:
            value = self.env.get(var, "").strip()
            if not value:
                continue

            # Assume it's not for windows, for now.  Can't instantiate
            # WindowsPath on linux anyway:
            if value.startswith(os.sep):
                try:
                    path = pathlib.Path(value)
                except ValueError:
                    ...
                else:
                    if not check or (path / "Makefile").is_file():
                        results[var] = path

        return results

    @classmethod
    def _get_section(cls, output: str, section: str) -> str:
        """Get a single make output section."""
        return "\n".join(
            lines_between(
                output,
                start_marker=_section_start_marker + section,
                end_marker=_section_end_marker,
                include_blank=False,
            )
        ).strip()

    @classmethod
    def _get_env(cls, output: str, keep_os_env: bool = False) -> Dict[str, str]:
        """Get environment variables from make output."""
        env = {}
        for line in sorted(cls._get_section(output, "env").split("\0")):
            if "=" in line:
                variable, value = line.split("=", 1)
                if not keep_os_env and os.environ.get(variable) == value:
                    ...
                else:
                    env[variable] = value
        return env

    @classmethod
    def _get_make_vars(cls, output: str) -> Dict[str, str]:
        """Get environment variables from make output."""
        makevars = {
            var: cls._get_section(output, var)
            for var in (
                "default_goal",
                "makefile_list",
                "make_features",
                "include_dirs",
            )
        }

        if makevars.get("default_goal", None) == _whatrecord_target:
            # This means there's no default goal, and ours is the first
            makevars["default_goal"] = ""

        return makevars

    @classmethod
    def _from_make_output(
        cls,
        output: str,
        filename: Optional[AnyPath] = None,
        keep_os_env: bool = False,
    ) -> Makefile:
        """
        Parse ``make`` output with our helper target attached.
        """
        if filename is not None:
            filename = pathlib.Path(filename)

        try:
            env = cls._get_env(output, keep_os_env=keep_os_env)
            make_vars = cls._get_make_vars(output)
            return cls(
                env=env,
                filename=filename,
                default_goal=make_vars.get("default_goal", ""),
                makefile_list=make_vars.get("makefile_list", "").split(),
                make_features=set(make_vars.get("make_features", "").split()),
                include_dirs=make_vars.get("include_dirs", "").split(),
                build_archs=env.get("BUILD_ARCHS", "").split(),
                cross_compiler_host_archs=env.get("CROSS_COMPILER_HOST_ARCHS", "").split(),
                cross_compiler_target_archs=env.get("CROSS_COMPILER_TARGET_ARCHS", "").split(),
                base_version=env.get("BASE_MODULE_VERSION", ""),
                base_config_path=pathlib.Path(env["CONFIG"]) if "CONFIG" in env else None,
                release_top_vars=env.get("RELEASE_TOPS", "").split(),
            )
        except Exception:
            logger.exception("Failed to parse Makefile output: %s", output)
            return Makefile(filename=filename)

    @classmethod
    def from_string(
        cls,
        contents: str,
        filename: Optional[AnyPath] = None,
        working_directory: Optional[AnyPath] = None,
        keep_os_env: bool = False,
        encoding: str = "utf-8",
    ) -> Makefile:
        """
        Get Makefile information given its contents.

        Parameters
        ----------
        contents : str
            The Makefile contents.

        filename : pathlib.Path or str, optional
            The filename.

        working_directory : pathlib.Path or str, optional
            The working directory to use when evaluating the Makefile contents.
            Assumed to be the directory in which the makefile is contained, but
            this may be overridden.  If the filename is unavailable, the
            fallback is the current working directory.

        keep_os_env : bool, optional
            Keep environment variables in ``.env`` from outside of ``make``,
            as in those present in ``os.environ`` when executing ``make``.

        encoding : str, optional
            String encoding to use.

        Raises
        ------
        RuntimeError
            If unable to run ``make`` and get information.

        Returns
        -------
        makefile : Makefile
            The makefile information.
        """
        if not host_has_make():
            raise MakeNotInstalled("Host does not have ``make`` installed.")

        full_contents = "\n".join((contents, _make_helper))
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "New makefile contents: %s",
                full_contents.replace("\t", "(tab) "),
            )

        if working_directory is None:
            if filename is not None:
                working_directory = pathlib.Path(filename).resolve().parent
            else:
                working_directory = pathlib.Path.cwd()

        result = subprocess.run(
            ["make", "--silent", "--file=-", _whatrecord_target],
            input=full_contents.encode(encoding),
            cwd=working_directory,
            capture_output=True,
        )
        stdout = result.stdout.decode(encoding, "replace")
        if logger.isEnabledFor(logging.DEBUG):
            stderr = result.stderr.decode(encoding, "replace")
            logger.debug(
                "make output:\n%s\nmake stderr:\n%s",
                textwrap.indent(stdout, "    "),
                textwrap.indent(stderr, "    ")
            )
        return cls._from_make_output(stdout, filename=filename)

    @classmethod
    def from_file_obj(
        cls,
        fp,
        filename: Optional[AnyPath] = None,
        working_directory: Optional[AnyPath] = None,
        keep_os_env: bool = False,
        encoding: str = "utf-8",
    ) -> Makefile:
        """
        Load a Makefile from a file object.

        Parameters
        ----------
        fp : file-like object
            The file-like object to read from.

        filename : pathlib.Path or str, optional
            The filename, defaults to ``fp.name`` if available.

        working_directory : pathlib.Path or str, optional
            The working directory to use when evaluating the Makefile contents.
            Assumed to be the directory in which the makefile is contained, but
            this may be overridden.  If the filename is unavailable, the
            fallback is the current working directory.

        keep_os_env : bool, optional
            Keep environment variables in ``.env`` from outside of ``make``,
            as in those present in ``os.environ`` when executing ``make``.

        encoding : str, optional
            String encoding to use.

        Raises
        ------
        RuntimeError
            If unable to run ``make`` and get information.

        Returns
        -------
        makefile : Makefile
            The makefile information.
        """
        return cls.from_string(
            fp.read(),
            filename=filename or getattr(fp, "name", None),
            working_directory=working_directory,
            encoding=encoding,
            keep_os_env=keep_os_env,
        )

    @classmethod
    def from_file(
        cls,
        filename: AnyPath,
        working_directory: Optional[AnyPath] = None,
        keep_os_env: bool = False,
        encoding: str = "utf-8",
    ) -> Makefile:
        """
        Load a Makefile from a filename.

        Parameters
        ----------
        filename : pathlib.Path or str
            The filename.

        working_directory : pathlib.Path or str, optional
            The working directory to use when evaluating the Makefile contents.
            Assumed to be the directory in which the makefile is contained, but
            this may be overridden.

        keep_os_env : bool, optional
            Keep environment variables in ``.env`` from outside of ``make``,
            as in those present in ``os.environ`` when executing ``make``.

        encoding : str, optional
            String encoding to use.

        Raises
        ------
        RuntimeError
            If unable to run ``make`` and get information.

        Returns
        -------
        makefile : Makefile
            The makefile information.
        """
        with open(filename, "rt") as fp:
            contents = fp.read()
        return cls.from_string(
            contents,
            filename=filename,
            working_directory=working_directory,
            encoding=encoding,
            keep_os_env=keep_os_env,
        )

    @staticmethod
    def find_makefile(
        file_or_directory: AnyPath,
    ) -> pathlib.Path:
        """
        Find a Makefile given a path, if it exists.

        Accepts either a direct path to a Makefile or a directory containing
        a Makefile.

        Parameters
        ----------
        file_or_directory : str or pathlib.Path
            Makefile directory or direct path.

        Raises
        ------
        FileNotFoundError
            If the file or directory does not contain a ``Makefile``.
        """
        path = pathlib.Path(file_or_directory)

        if path.is_dir():
            path = path / "Makefile"

        if not path.exists():
            raise FileNotFoundError(file_or_directory)

        return path.resolve()


@dataclass
class Dependency:
    """A single EPICS dependency (module) in the build system."""
    #: The name of the dependency, as derived from the path name
    name: str = ""
    #: The name of the dependency, as derived from the build system variable
    variable_name: Optional[str] = None
    #: The absolute path to the dependency
    path: pathlib.Path = field(default_factory=pathlib.Path)
    #: The parsed Makefile information for this dependency
    makefile: Makefile = field(default_factory=Makefile)
    #: Modules (etc.) which depend on this instance
    dependents: List[pathlib.Path] = field(default_factory=list)
    #: Modules (etc.) are required for this instance
    dependencies: List[pathlib.Path] = field(default_factory=list)
    #: The "root" node.  ``None`` to refer to itself.
    root: Optional[DependencyGroup] = field(default=None, metadata=apischema.metadata.skip)

    @classmethod
    def from_makefile(
        cls,
        makefile: Makefile,
        recurse: bool = True,
        *,
        keep_os_env: bool = False,
        name: Optional[str] = None,
        variable_name: Optional[str] = None,
        root: Optional[DependencyGroup] = None,
    ) -> Dependency:
        if makefile.filename is not None:
            name = name or makefile.filename.parent.name
            path = makefile.filename.parent
        else:
            name = name or "unknown"
            path = pathlib.Path(".")  # :shrug:

        this_dep = Dependency(
            name=name,
            variable_name=variable_name,
            path=path,
            makefile=makefile,
            dependents=[],
            dependencies=[],
            root=root,
        )

        if root is not None:
            root.all_modules[this_dep.path] = this_dep

        if not recurse:
            return this_dep

        for variable_name, path in makefile.find_release_paths().items():
            if root and path in root.all_modules:
                continue

            try:
                dep_makefile_path = Makefile.find_makefile(path)
            except FileNotFoundError:
                continue

            dep_makefile = Makefile.from_file(
                dep_makefile_path, keep_os_env=keep_os_env
            )
            release_dep = Dependency.from_makefile(
                dep_makefile,
                recurse=True,
                keep_os_env=keep_os_env,
                name=variable_name,
                variable_name=variable_name,
                root=root,
            )
            release_dep.dependents.append(this_dep.path)
            this_dep.dependencies.append(release_dep.path)

        return this_dep


@dataclass
class DependencyGroup:
    """
    IOC (or support module) dependency information.

    This differs
    """
    #: The primary IOC or module this refers to.
    root: pathlib.Path
    #: All modules found while scanning for the root one.
    all_modules: Dict[pathlib.Path, Dependency] = field(default_factory=dict)

    @classmethod
    def from_makefile(
        cls,
        makefile: Makefile,
        recurse: bool = True,
        *,
        keep_os_env: bool = False,
        name: Optional[str] = None,
    ) -> DependencyGroup:
        if makefile.filename is None:
            raise ValueError("The provided Makefile must have a path")

        info = cls(root=makefile.filename.parent, all_modules={})
        # The following will implicitly be inserted into all_modules
        Dependency.from_makefile(
            makefile=makefile,
            name=name,
            keep_os_env=keep_os_env,
            root=info,
            recurse=recurse,
        )
        return info

    def as_graph(self, **kwargs) -> DependencyGroupGraph:
        """
        Create a graphviz digraph of the dependencies.

        Returns
        -------
        graph : DependencyGroupGraph
        """
        return DependencyGroupGraph(self, **kwargs)


class DependencyGroupGraph(_GraphHelper):
    """
    A graph for a group of dependencies.

    Parameters
    ----------
    dep : Dependency or DependencyGroup, optional
        A dep to add.

    highlight_states : list of str, optional
        List of state names to highlight.

    include_code : bool, optional
        Include code, where relevant, in nodes.
    """

    _entry_label: str = "_Entry_"
    _exit_label: str = "_Exit_"

    def __init__(
        self,
        dep: Optional[Union[Dependency, DependencyGroup]] = None,
        highlight_deps: Optional[List[str]] = None,
        include_code: bool = False,
    ):
        super().__init__()
        self.include_code = include_code
        self.highlight_deps = highlight_deps or []
        if dep is not None:
            self.add_dependency(dep)

    def add_dependency(self, item: Union[DependencyGroup, Dependency]):
        """Add a dependency to the graph."""
        if isinstance(item, DependencyGroup):
            for path, mod in item.all_modules.items():
                self.add_dependency(mod)
            return

        if item.path in self.nodes:
            return

        self.get_node(
            str(item.path), text=f"{item.variable_name} {item.name}\n{item.path}"
        )
        if item.root is None:
            # Misconfiguration?
            return

        for dep_path in item.dependencies:
            dep = item.root.all_modules[dep_path]
            self.add_dependency(dep)
            self.add_edge(str(item.path), str(dep.path))

    def _ready_for_digraph(self, graph: gv.Digraph):
        """Hook when the user calls ``to_digraph``."""
        for node in self.nodes.values():
            node.highlighted = node.label in self.highlight_deps
