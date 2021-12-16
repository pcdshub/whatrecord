"""
"whatrecord graph" is used to parse and generate a relationship graph of
whatrecord-supported file types.
"""

import argparse
import logging
import re
from typing import Dict, List, Optional

# from ..access_security import AccessSecurityConfig
from ..common import AnyPath, RecordInstance  # , FileFormat, IocMetadata
from ..db import Database, LinterResults
# from ..dbtemplate import TemplateSubstitution
# from ..format import FormatContext
# from ..gateway import PVList as GatewayPVList
from ..graph import build_database_relations, graph_links
# from ..macro import MacroContext
from ..shell import LoadedIoc
# from ..snl import SequencerProgram
# from ..streamdevice import StreamProtocol
from .parse import parse_from_cli_args

logger = logging.getLogger(__name__)
DESCRIPTION = __doc__


def build_arg_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    parser.description = DESCRIPTION
    parser.formatter_class = argparse.RawTextHelpFormatter

    parser.add_argument(
        "filenames",
        type=str,
        nargs="+",
        help="Script or database filename(s)"
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

    parser.add_argument(
        "--highlight",
        nargs="*",
        type=str,
        default=(".*", ),
        help="Highlight the provided regular expression matches",
    )

    return parser


def _combine_databases(*items: Database) -> Database:
    for item in items:
        if not isinstance(item, (Database, LinterResults)):
            raise ValueError(f"Expected Database, got {type(item)}")

    db = items[0]
    for item in items[1:]:
        for record, instance in item.records.items():
            existing_record = db.records.get(record, None)
            if not existing_record:
                db.records[record] = instance
            else:
                existing_record.info.update(instance.info)
                existing_record.metadata.update(instance.metadata)
                existing_record.fields.update(instance.fields)
                existing_record.aliases = list(
                    sorted(set(existing_record.aliases + instance.aliases))
                )
                if existing_record.record_type != instance.record_type:
                    logger.warning(
                        "Record type mismatch in provided database files: "
                        "%s %s %s",
                        record, instance.record_type, existing_record.record_type
                    )

        db.record_types.update(item.record_types or {})

    return db


def main(
    filenames: List[AnyPath],
    dbd: Optional[str] = None,
    standin_directory: Optional[List[str]] = None,
    macros: Optional[str] = None,
    friendly: bool = False,
    use_gdb: bool = False,
    format: Optional[str] = None,
    expand: bool = False,
    friendly_format: str = "console",
    highlight: Optional[List[str]] = None,
    only: Optional[List[str]] = None,
    v3: bool = False,
):
    highlight = highlight or []
    only = only or []

    databases_only = len(filenames) > 1
    results = [
        parse_from_cli_args(
            filename=filename,
            dbd=dbd,
            standin_directory=standin_directory,
            macros=macros,
            use_gdb=use_gdb,
            format=format,
            expand=expand,
            v3=v3,
        )
        for filename in filenames
    ]

    if databases_only:
        result = _combine_databases(*results)
    else:
        result, = results

    if isinstance(result, (LinterResults, LoadedIoc, Database)):
        if isinstance(result, LoadedIoc):
            database = result.shell_state.database
            defn = result.shell_state.database_definition
            record_types = defn.record_types if defn else None
            aliases = result.shell_state.aliases
        elif isinstance(result, LinterResults):
            database = result.records
            record_types = result.record_types
            aliases = {}
        else:
            database = result.records
            record_types = result.record_types
            aliases = result.aliases

        def records_by_patterns(patterns: List[str]) -> Dict[str, RecordInstance]:
            return {
                rec.name: rec
                for rec in database.values()
                if any(
                    re.search(pattern, rec.name)
                    for pattern in highlight
                )
            }

        starting_records = records_by_patterns(highlight) if highlight else []
        relations = build_database_relations(
            database=database,
            record_types=record_types,
            aliases=aliases,
        )
        node, edges, graph = graph_links(
            database=database,
            starting_records=starting_records,
            relations=relations,
        )
        print(graph.source)
    else:
        raise RuntimeError(
            f"Sorry, graph isn't supported yet for {result.__class__.__name__}"
        )
