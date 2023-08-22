"""
"whatrecord parse" is used to parse and interpret any of whatrecord's supported
file formats, dumping the results to the console (standard output) in JSON
format, by default.

Unless ``--disable-macros`` is specified, all text will go through the macro
context as if the files were being loaded in an IOC shell.
"""

import argparse
import json
import logging
from typing import List, Optional

from ..common import AnyPath, FileFormat, IocMetadata
from ..parse import ParseResult, parse
from ..shell import LoadedIoc
from ..util import write_to_file

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
        "-if",
        "--input-format",
        type=str,
        required=False,
        help=(
            "The file format.  For files that lack a recognized extension or "
            "are otherwise misidentified by whatrecord."
        ),
    )

    parser.add_argument(
        "--v3",
        action="store_true",
        help="Use V3 database grammar instead of V4 where possible"
    )

    parser.add_argument(
        "--dbd",
        type=str,
        help="The dbd file, if parsing a database",
    )

    parser.add_argument(
        "--standin-directory",
        type=str,
        nargs="*",
        help='Map a "stand-in" directory to another on disk',
    )

    parser.add_argument(
        "--macros",
        type=str,
        help="Macro to add, in the usual form ``macro=value,...``",
    )

    parser.add_argument(
        "--disable-macros",
        action="store_true",
        help="Disable macro handling, leaving unexpanded macros in the output."
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        required=False,
        help="Output file to write to.  Defaults to standard output.",
    )

    parser.add_argument(
        "-of", "--output-format",
        type=str,
        default="json",
        help=(
            "Defaults to 'json', some input formats may support "
            "'console', which aims to be convenient for console output, "
            "or 'file', which should closely resemble the input file"
        ),
    )

    parser.add_argument(
        '--use-gdb',
        action="store_true",
        help="Use metadata derived from the script binary",
    )

    parser.add_argument(
        "--expand",
        action="store_true",
        help="Expand a substitutions file, as in the msi tool",
    )

    return parser


def parse_from_cli_args(
    filename: AnyPath,
    dbd: Optional[str] = None,
    standin_directory: Optional[List[str]] = None,
    macros: Optional[str] = None,
    disable_macros: bool = False,
    use_gdb: bool = False,
    format: Optional[str] = None,
    expand: bool = False,
    v3: bool = False,
) -> ParseResult:
    """
    Generically parse either a startup script or a database file.

    This variant uses the raw CLI arguments, mapping them on to those that
    `parse` expects.  For programmatic usage, please use ``parse()`` directly.

    Unless ``disable_macros`` is set, all text will go through the macro
    context as if the files were being loaded in an IOC shell.

    Parameters
    ----------
    filename : str or pathlib.Path
        The filename to parse.

    dbd : str or pathlib.Path, optional
        The associated database definition file, if parsing a database file.

    standin_directories : list, optional
        A list of substitute directories of the form ``DirectoryA=DirectoryB``.

    macros : str, optional
        Macro string to use when parsing the file.  Ignored if
        ``disable_macros`` is set.

    disable_macros : bool, optional
        Disable macro handling, leaving unexpanded macros in the output.

    expand : bool, optional
        Expand a substitutions file.

    v3 : bool, optional
        Use V3 database grammar where applicable.
    """
    standin_directories = dict(
        path.split("=", 1) for path in standin_directory or ""
    )

    if isinstance(filename, str) and filename.startswith("{"):   # }
        # TODO - argparse fixup?
        ioc_metadata = IocMetadata.from_dict(json.loads(filename))
        # TODO macros, use_gdb, ...
        # ioc_metadata.macros = macros
        return LoadedIoc.from_metadata(
            ioc_metadata
        )

    try:
        format = FileFormat(format) if format is not None else None
    except ValueError:
        options = [fmt.name for fmt in list(FileFormat)]
        raise ValueError(
            f"{format!r} is not a valid FileFormat. Options include: "
            f"{options}"
        )

    return parse(
        filename,
        dbd=dbd,
        standin_directories=standin_directories,
        macros=macros,
        disable_macros=disable_macros,
        use_gdb=use_gdb,
        format=format,
        expand=expand,
        v3=v3,
    )


def main(
    filename: AnyPath,
    dbd: Optional[str] = None,
    standin_directory: Optional[List[str]] = None,
    input_format: Optional[str] = None,
    output_format: str = "json",
    output: Optional[str] = None,
    macros: Optional[str] = None,
    disable_macros: bool = False,
    use_gdb: bool = False,
    expand: bool = False,
    v3: bool = False,
):
    result = parse_from_cli_args(
        filename=filename,
        dbd=dbd,
        standin_directory=standin_directory,
        macros=macros,
        disable_macros=disable_macros,
        use_gdb=use_gdb,
        format=input_format,
        expand=expand,
        v3=v3,
    )

    write_to_file(result, filename=output, format=output_format)
