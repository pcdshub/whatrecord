"""
"whatrecord lint" is used to lint a startup script or database file.
"""

import argparse
import logging
import pathlib
import sys
from typing import IO, List, Optional, Union

from ..db import Database
from ..format import FormatContext
from ..shell import LoadedIoc
from .parse import parse_from_cli_args

logger = logging.getLogger(__name__)
DESCRIPTION = __doc__


def build_arg_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    parser.description = DESCRIPTION
    parser.formatter_class = argparse.RawTextHelpFormatter

    parser.add_argument(
        'filename',
        type=str,
        help="Startup script filename"
    )

    parser.add_argument(
        '--dbd',
        type=str,
        help="The dbd file, if parsing a database",
    )

    parser.add_argument(
        '--standin-directory',
        type=str,
        nargs='*',
        help='Map a "stand-in" directory to another on disk'
    )

    parser.add_argument(
        '--json',
        dest="as_json",
        action="store_true",
    )

    parser.add_argument(
        '-v', '--verbose',
        dest="verbosity",
        action="count",
        help="Increase verbosity"
    )

    return parser


def lint(
    obj: Union[Database, LoadedIoc],
    *,
    verbosity: int = 0,
    file: IO[str] = sys.stdout,
    fmt: FormatContext = None,
) -> Union[Database, LoadedIoc]:
    """
    Lint a startup script or a database file.

    Parameters
    ----------
    obj :
        The object to lint.
    """
    fmt = fmt or FormatContext()
    if isinstance(obj, LoadedIoc):
        for line in obj.script.lines:
            if line.line or verbosity > 2:
                if line.error or verbosity > 1:
                    print(fmt.render_object(line).rstrip(), file=file)


def main(
    filename: Union[str, pathlib.Path],
    dbd: Optional[str] = None,
    standin_directory: Optional[List[str]] = None,
    macros: Optional[str] = None,
    as_json: bool = False,
    verbosity: Optional[int] = 0,
):
    obj = parse_from_cli_args(
        filename=filename,
        dbd=dbd,
        standin_directory=standin_directory,
        macros=macros,
    )
    lint(obj, verbosity=verbosity or 0)
