"""
"whatrecord lint" is used to lint a startup script or database file.
"""

import argparse
import logging
import pathlib
import sys
from typing import IO, List, Optional, Union

from ..common import IocshCommand
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

    parser.add_argument(
        '--use-gdb',
        action="store_true",
        help="Use metadata derived from the script binary",
    )

    return parser


def lint_command(
    command_info: IocshCommand,
    argv: List[str],
    file: IO[str] = sys.stdout,
    fmt: FormatContext = None,
):
    """Lint a command given its argumenet information."""
    if not command_info:
        print(f"  ! Warning: Unknown command: {argv[0]}")
        return

    expected_args = command_info.args
    actual_args = argv[1:]
    arg_names = [arg.name for arg in expected_args]
    if len(actual_args) == len(expected_args):
        return

    if len(actual_args) < len(expected_args):
        arg_names = [arg.name for arg in expected_args]
        arg_values = list(actual_args) + ["?"] * (len(expected_args) - len(actual_args))
        print("  ! Warning: may be too few arguments", file=file)
    else:
        print("  ! Warning: too many arguments", file=file)
        arg_names = [
            arg.name for arg in expected_args
        ] + ["?"] * (len(actual_args) - len(expected_args))
        arg_values = actual_args

    for idx, (arg_name, value) in enumerate(zip(arg_names, arg_values), 1):
        print(f"    {idx}. {arg_name} = {value}", file=file)
    print(file=file)


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
        commands = obj.metadata.commands
        # variables = obj.metadata.variables
        for line in obj.script.lines:
            if line.line or verbosity > 2:
                if line.error or verbosity > 1:
                    print(fmt.render_object(line).rstrip(), file=file)
                if commands and line.argv:
                    command_info = commands.get(line.argv[0], None)
                    lint_command(command_info=command_info, argv=line.argv, file=file, fmt=fmt)


def main(
    filename: Union[str, pathlib.Path],
    dbd: Optional[str] = None,
    standin_directory: Optional[List[str]] = None,
    macros: Optional[str] = None,
    as_json: bool = False,
    use_gdb: bool = False,
    verbosity: Optional[int] = 0,
):
    obj = parse_from_cli_args(
        filename=filename,
        dbd=dbd,
        standin_directory=standin_directory,
        macros=macros,
        use_gdb=use_gdb,
    )
    lint(obj, verbosity=verbosity or 0)
