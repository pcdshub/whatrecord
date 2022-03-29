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

{_whatrecord_target}:
    @echo "{_section_start_marker}env"
    @env -0
    @echo "{_section_end_marker}env"
    @echo "{_section_start_marker}make"
    @echo -e "default_goal=$(.DEFAULT_GOAL)\\0"
    @echo "{_section_end_marker}make"
""".replace("    ", "\t")


@dataclass
class MakefileInformation:
    """
    Makefile information as determined by ``make`` itself.
    """

    env: Dict[str, str] = field(default_factory=dict)
    make_vars: Dict[str, str] = field(default_factory=dict)
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
    def from_make_output(
        cls, output: str, filename: Optional[AnyPath] = None
    ) -> MakefileInformation:
        if filename is not None:
            filename = pathlib.Path(filename)

        return cls(
            env=cls._get_env(output),
            make_vars=cls._get_make_vars(output),
            filename=filename,
        )

    @classmethod
    def from_makefile_contents(
        cls, contents: str, filename: Optional[AnyPath] = None, encoding: str = "utf-8"
    ) -> MakefileInformation:
        full_contents = "\n".join((contents, _make_helper))
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "New makefile contents: %s",
                full_contents.replace("\t", "(tab) "),
            )
        output = subprocess.check_output(
            ["make", "--silent", "--file=-", _whatrecord_target],
            input=full_contents.encode(encoding),
        )
        output = output.decode(encoding)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "make output:\n%s",
                textwrap.indent(output, "    ")
            )
        return cls.from_make_output(output, filename=filename)

    @classmethod
    def from_makefile(cls, filename: AnyPath, encoding: str = "utf-8") -> MakefileInformation:
        with open(filename, "rt") as fp:
            contents = fp.read()
        return cls.from_makefile_contents(contents, filename=filename, encoding=encoding)
