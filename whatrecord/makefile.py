from __future__ import annotations

import logging
import pathlib
import subprocess
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .common import AnyPath
from .util import lines_between

logger = logging.getLogger(__name__)

_section_start_marker = "--whatrecord-section-start--"
_section_end_marker = "--whatrecord-section-end--"
_whatrecord_target = "_whatrecord_target"

_make_helper: str = f"""

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
    @echo "{_section_end_marker}env"
    # This is the make meta information section, as specified by make itself
    @echo "{_section_start_marker}make"
    @echo -e "default_goal=$(.DEFAULT_GOAL)\\0"
    @echo -e "makefile_list=$(MAKEFILE_LIST)\\0"
    @echo -e "features=$(.FEATURES)\\0"
    @echo -e "include_dirs=$(.INCLUDE_DIRS)\\0"
    @echo "{_section_end_marker}make"
""".replace("    ", "\t")


@dataclass
class MakefileInformation:
    """
    Makefile information as determined by ``make`` itself.

    Will not work if:
    * ``.RECIPEPREFIX`` is set to anything but tab in the makefile, however
        uncommon that may be.
    """

    #: Environment variable name to value.
    env: Dict[str, str] = field(default_factory=dict)
    #: Special make variable information.
    make_vars: Dict[str, str] = field(default_factory=dict)
    #: The Makefile filename, if available.
    filename: Optional[pathlib.Path] = None

    @classmethod
    def _get_section(cls, output: str, section: str) -> List[str]:
        """Get a single make output section."""
        return list(
            lines_between(
                output,
                start_marker=_section_start_marker + section,
                end_marker=_section_end_marker + section,
                include_blank=False,
            )
        )

    @classmethod
    def _get_env(cls, output: str) -> Dict[str, str]:
        """Get environment variables from make output."""
        env = {}
        env_lines = "\0".join(cls._get_section(output, "env"))
        for line in env_lines.split("\0"):
            if "=" in line:
                variable, value = line.split("=", 1)
                env[variable] = value
        return env

    @classmethod
    def _get_make_vars(cls, output: str) -> Dict[str, str]:
        """Get environment variables from make output."""
        makevars = {}
        env_lines = "\0".join(cls._get_section(output, "make"))
        for line in env_lines.split("\0"):
            if "=" in line:
                variable, value = line.split("=", 1)
                makevars[variable] = value

        if makevars.get("default_goal", None) == _whatrecord_target:
            # This means there's no default goal, and ours is the first
            makevars["default_goal"] = ""

        return makevars

    @classmethod
    def _from_make_output(
        cls, output: str, filename: Optional[AnyPath] = None
    ) -> MakefileInformation:
        """
        Parse ``make`` output with our helper target attached.
        """
        if filename is not None:
            filename = pathlib.Path(filename)

        try:
            return cls(
                env=cls._get_env(output),
                make_vars=cls._get_make_vars(output),
                filename=filename,
            )
        except Exception:
            logger.exception("Failed to parse Makefile output: %s", output)
            return MakefileInformation(filename=filename)

    @classmethod
    def from_string(
        cls, contents: str, filename: Optional[AnyPath] = None, encoding: str = "utf-8"
    ) -> MakefileInformation:
        """
        Get Makefile information given its contents.

        Parameters
        ----------
        contents : str
            The Makefile contents.

        filename : pathlib.Path or str, optional
            The filename.

        encoding : str, optional
            Encoding to use.

        Raises
        ------
        RuntimeError
            If unable to run ``make`` and get information.

        Returns
        -------
        makefile : MakefileInformation
            The makefile information.
        """
        full_contents = "\n".join((contents, _make_helper))
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "New makefile contents: %s",
                full_contents.replace("\t", "(tab) "),
            )
        result = subprocess.run(
            ["make", "--silent", "--file=-", _whatrecord_target],
            input=full_contents.encode(encoding),
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
        cls, fp, filename: Optional[AnyPath] = None, encoding: str = "utf-8"
    ) -> MakefileInformation:
        """
        Load a Makefile from a file object.

        Parameters
        ----------
        fp : file-like object
            The file-like object to read from.

        filename : pathlib.Path or str, optional
            The filename, defaults to ``fp.name`` if available.

        encoding : str, optional
            Encoding to use.

        Raises
        ------
        RuntimeError
            If unable to run ``make`` and get information.

        Returns
        -------
        makefile : MakefileInformation
            The makefile information.
        """
        return cls.from_string(
            fp.read(),
            filename=filename or getattr(fp, "name", None),
            encoding=encoding,
        )

    @classmethod
    def from_file(
        cls, filename: AnyPath, encoding: str = "utf-8"
    ) -> MakefileInformation:
        """
        Load a Makefile from a filename.

        Parameters
        ----------
        filename : pathlib.Path or str
            The filename.

        encoding : str, optional
            Encoding to use.

        Raises
        ------
        RuntimeError
            If unable to run ``make`` and get information.

        Returns
        -------
        makefile : MakefileInformation
            The makefile information.
        """
        with open(filename, "rt") as fp:
            contents = fp.read()
        return cls.from_string(contents, filename=filename, encoding=encoding)
