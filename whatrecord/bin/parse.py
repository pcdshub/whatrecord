"""
"whatrecord parse" is used to parse and interpret any of whatrecord's supported
file formats, dumping the results to the console (standard output) in JSON
format, by default.
"""

import argparse
import json
import logging
from typing import List, Optional

import apischema

from ..common import AnyPath, FileFormat, IocMetadata
from ..format import FormatContext
from ..parse import ParseResult, parse
from ..shell import LoadedIoc

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
        "--format",
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
        "--friendly",
        action="store_true",
        help="Output Python object representation instead of JSON",
    )

    parser.add_argument(
        "--friendly-format",
        type=str,
        default="console",
        help="Output Python object representation instead of JSON",
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
    use_gdb: bool = False,
    format: Optional[str] = None,
    expand: bool = False,
    v3: bool = False,
) -> ParseResult:
    """
    Generically parse either a startup script or a database file.

    This variant uses the raw CLI arguments, mapping them on to those that
    `parse` expects.  For programmatic usage, please use ``parse()`` directly.

    Parameters
    ----------
    filename : str or pathlib.Path
        The filename to parse.

    dbd : str or pathlib.Path, optional
        The associated database definition file, if parsing a database file.

    standin_directories : list, optional
        A list of substitute directories of the form ``DirectoryA=DirectoryB``.

    macros : str, optional
        Macro string to use when parsing the file.

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
        use_gdb=use_gdb,
        format=format,
        expand=expand,
        v3=v3,
    )


def main(
    filename: AnyPath,
    dbd: Optional[str] = None,
    standin_directory: Optional[List[str]] = None,
    macros: Optional[str] = None,
    friendly: bool = False,
    use_gdb: bool = False,
    format: Optional[str] = None,
    expand: bool = False,
    friendly_format: str = "console",
    v3: bool = False,
):
    result = parse_from_cli_args(
        filename=filename,
        dbd=dbd,
        standin_directory=standin_directory,
        macros=macros,
        use_gdb=use_gdb,
        format=format,
        expand=expand,
        v3=v3,
    )

    if friendly:
        fmt = FormatContext()
        print(fmt.render_object(result, friendly_format))
    else:
        # TODO: JSON -> obj -> JSON round tripping
        json_info = apischema.serialize(result)
        print(json.dumps(json_info, indent=4))
