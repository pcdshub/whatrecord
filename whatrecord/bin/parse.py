"""
"whatrecord parse" is used to parse and interpret any of whatrecord's supported
file formats, dumping the results to the console (standard output) in JSON
format, by default.
"""

import argparse
import asyncio
import json
import logging
import pathlib
from typing import Dict, List, Optional, Union

import apischema

from ..access_security import AccessSecurityConfig
from ..common import AnyPath, FileFormat, IocMetadata
from ..db import Database, LinterResults
from ..dbtemplate import TemplateSubstitution
from ..format import FormatContext
from ..gateway import PVList as GatewayPVList
from ..macro import MacroContext
from ..shell import LoadedIoc
from ..streamdevice import StreamProtocol

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


ParseResult = Union[
    AccessSecurityConfig,
    Database,
    GatewayPVList,
    LinterResults,
    LoadedIoc,
    StreamProtocol,
    TemplateSubstitution,
]


def parse(
    filename: AnyPath,
    dbd: Optional[str] = None,
    standin_directories: Optional[Dict[str, str]] = None,
    macros: Optional[str] = None,
    use_gdb: bool = False,
    format: Optional[FileFormat] = None,
    expand: bool = False,
) -> ParseResult:
    """
    Generically parse either a startup script or a database file.

    Hopefully does the right thing based on file extension.  If not, use
    the ``format`` kwarg to specify it directly.

    Parameters
    ----------
    filename : str or pathlib.Path
        The filename to parse.

    dbd : str or pathlib.Path, optional
        The associated database definition file, if parsing a database or
        substitutions file.

    standin_directories : dict, optional
        Rewrite hard-coded directory prefixes by setting::

            standin_directories = {"/replace_this/": "/with/this"}

    macros : str, optional
        Macro string to use when parsing the file.

    expand : bool, optional
        Expand a substitutions file.
    """
    standin_directories = standin_directories or {}

    filename = pathlib.Path(filename)

    # The shared macro context - used in different ways below:
    macro_context = MacroContext(macro_string=macros or "")

    if format is None:
        format = FileFormat.from_filename(filename)

    if format in (FileFormat.database, FileFormat.database_definition):
        if format == FileFormat.database_definition or not dbd:
            return Database.from_file(filename, macro_context=macro_context)
        return LinterResults.from_database_file(
            db=filename,
            dbd=Database.from_file(dbd),
            macro_context=macro_context
        )

    if format == FileFormat.iocsh:
        md = IocMetadata.from_filename(
            filename,
            standin_directories=standin_directories,
            macros=dict(macro_context),
        )
        if use_gdb:
            try:
                asyncio.run(md.get_binary_information())
            except KeyboardInterrupt:
                logger.info("Skipping gdb information...")

        return LoadedIoc.from_metadata(md)

    if format == FileFormat.substitution:
        template = TemplateSubstitution.from_file(filename)
        if not expand:
            return template

        database_text = template.expand_files()
        # It's technically possible that this *isn't* a database file; so
        # perhaps a `whatrecord msi` could be implemented in the future.
        return Database.from_string(
            database_text,
            macro_context=macro_context,
            dbd=Database.from_file(dbd) if dbd is not None else None,
            filename=filename,
        )

    with open(filename, "rt") as fp:
        contents = fp.read()

    if macros:
        contents = macro_context.expand_file(contents)

    if format == FileFormat.gateway_pvlist:
        return GatewayPVList.from_string(contents, filename=filename)

    if format == FileFormat.access_security:
        return AccessSecurityConfig.from_string(contents, filename=filename)

    if format == FileFormat.stream_protocol:
        return StreamProtocol.from_string(contents, filename=filename)

    raise RuntimeError(
        f"Sorry, whatrecord doesn't support the {format!r} format just yet in the "
        f"CLI parsing tool.  Please open an issue."
    )


def parse_from_cli_args(
    filename: AnyPath,
    dbd: Optional[str] = None,
    standin_directory: Optional[List[str]] = None,
    macros: Optional[str] = None,
    use_gdb: bool = False,
    format: Optional[str] = None,
    expand: bool = False,
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

    return parse(
        filename,
        dbd=dbd,
        standin_directories=standin_directories,
        macros=macros,
        use_gdb=use_gdb,
        format=FileFormat(format) if format is not None else None,
        expand=expand,
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
):
    result = parse_from_cli_args(
        filename=filename,
        dbd=dbd,
        standin_directory=standin_directory,
        macros=macros,
        use_gdb=use_gdb,
        format=format,
        expand=expand,
    )

    if friendly:
        fmt = FormatContext()
        print(fmt.render_object(result, friendly_format))
    else:
        # TODO: JSON -> obj -> JSON round tripping
        json_info = apischema.serialize(result)
        print(json.dumps(json_info, indent=4))
