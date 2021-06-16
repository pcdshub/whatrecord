"""
"whatrec parse" is used to parse and interpret a startup script or database
file, dumping the resulting ``ShellState`` or ``Database``.
"""

import argparse
import json
import logging
import pathlib
from typing import Dict, List, Optional, Union

import apischema

from ..common import IocMetadata
from ..db import Database
from ..format import FormatContext
from ..macro import MacroContext
from ..shell import LoadedIoc, load_database_file

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

    return parser


def parse(
    filename: Union[str, pathlib.Path],
    dbd: Optional[str] = None,
    standin_directories: Optional[Dict[str, str]] = None,
    macros: Optional[str] = None,
) -> Union[Database, LoadedIoc]:
    """
    Generically parse either a startup script or a database file.

    Hopefully does the right thing based on file extension.

    Parameters
    ----------
    filename : str or pathlib.Path
        The filename to parse.

    dbd : str or pathlib.Path
        The associated database definition file, if parsing a database file.

    standin_directories : dict, optional

    macros : str, optional
    """
    standin_directories = standin_directories or {}

    filename = pathlib.Path(filename)
    macro_context = MacroContext()
    macro_context.define(**macro_context.definitions_to_dict(macros or ""))

    if filename.suffix in {".db", ".template", ".dbd"}:
        if filename.suffix == ".dbd" or not dbd:
            return Database.from_file(filename, macro_context=macro_context)
        return load_database_file(dbd=dbd, db=filename, macro_context=macro_context)
    return LoadedIoc.from_metadata(
        IocMetadata.from_filename(
            filename,
            standin_directories=standin_directories
        )
    )


def main(
    filename: Union[str, pathlib.Path],
    dbd: Optional[str] = None,
    standin_directory: Optional[List[str]] = None,
    macros: Optional[str] = None,
    as_json: bool = False,
):
    standin_directories = dict(
        path.split("=", 1) for path in standin_directory or ""
    )

    result = parse(
        filename,
        dbd=dbd,
        standin_directories=standin_directories,
        macros=macros,
    )

    if as_json:
        # TODO: JSON -> obj -> JSON round tripping
        json_info = apischema.serialize(result)
        print(json.dumps(json_info, indent=4))
    else:
        fmt = FormatContext()
        print(fmt.render_object(result, "console"))
