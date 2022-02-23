"""
"whatrecord graph" is used to parse and generate a relationship graph of
whatrecord-supported file types.
"""

import argparse
import logging
import pathlib
import re
import shutil
import tempfile
from typing import Dict, List, Optional, Tuple, Union

import graphviz as gv

from ..common import AnyPath, RecordInstance  # , FileFormat, IocMetadata
from ..db import Database, LinterResults
from ..graph import build_database_relations, graph_links
from ..shell import LoadedIoc
from ..snl import SequencerProgram
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
        "-o", "--output",
        type=str,
        required=False,
        help="Output file to write to.  Defaults to standard output.",
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

    parser.add_argument(
        "--code",
        action="store_true",
        help="Include code information in graph, where applicable"
    )

    return parser


def _combine_databases(*items: Database) -> Database:
    for item in items:
        if not isinstance(item, (Database, LinterResults)):
            raise ValueError(f"Expected Database, got {type(item)}")

    db = items[0]
    for item in items[1:]:
        db.append(item)

    return db


def render_graph_to_file(
    graph: gv.Digraph, default_format: str = "png", filename: Optional[str] = None
):
    if filename is None:
        print(graph.source)
        return

    output_extension = pathlib.Path(filename).suffix
    format = output_extension.lstrip(".").lower() or default_format
    if format == "dot":
        with open(filename, "wt") as fp:
            print(graph.source, file=fp)
    else:
        with tempfile.NamedTemporaryFile(suffix=f".{format}") as source_file:
            rendered_filename = graph.render(
                source_file.name, format=format
            )
        shutil.copyfile(rendered_filename, filename)


DatabaseItem = Union[LinterResults, LoadedIoc, Database]


def get_database_graph(
    *loaded_items: DatabaseItem,
    highlight: Optional[List[str]] = None,
) -> Tuple[dict, dict, gv.Digraph]:
    combined = _combine_databases(*loaded_items)
    if isinstance(combined, LoadedIoc):
        database = combined.shell_state.database
        defn = combined.shell_state.database_definition
        record_types = defn.record_types if defn else None
        aliases = combined.shell_state.aliases
    elif isinstance(combined, LinterResults):
        database = combined.records
        record_types = combined.record_types
        aliases = {}
    else:
        database = combined.records
        record_types = combined.record_types
        aliases = combined.aliases

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
    return graph_links(
        database=database,
        starting_records=starting_records,
        relations=relations,
    )


def main(
    filenames: List[AnyPath],
    dbd: Optional[str] = None,
    standin_directory: Optional[List[str]] = None,
    macros: Optional[str] = None,
    use_gdb: bool = False,
    format: Optional[str] = None,
    expand: bool = False,
    highlight: Optional[List[str]] = None,
    v3: bool = False,
    output: Optional[str] = None,
    code: bool = False,
):
    highlight = highlight or []

    databases_only = len(filenames) > 1
    loaded_items = [
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

    databases_only = all(
        isinstance(item, (LinterResults, LoadedIoc, Database))
        for item in loaded_items
    )

    if databases_only:
        nodes, edges, graph = get_database_graph(
            *loaded_items, highlight=highlight
        )
    else:
        try:
            item, = loaded_items
        except ValueError:
            raise RuntimeError(
                "Sorry, multiple database files are supported but only "
                "single files for other formats."
            )

        if isinstance(item, SequencerProgram):
            snl_graph = item.as_graph(include_code=code)
            nodes = snl_graph.nodes
            edges = snl_graph.edges
            graph = snl_graph.to_digraph()
        else:
            raise RuntimeError(
                f"Sorry, graph isn't supported yet for {item.__class__.__name__}"
            )

    render_graph_to_file(graph, filename=output)
    logger.debug("Nodes: %s", nodes)
    logger.debug("Edges: %s", edges)
