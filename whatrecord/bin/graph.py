"""
"whatrecord graph" is used to parse and generate a relationship graph of
whatrecord-supported file types.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import re
import shutil
import tempfile
from typing import List, Optional, Union

import graphviz as gv

from ..common import AnyPath
from ..db import Database, LinterResults
from ..graph import RecordLinkGraph, build_database_relations, graph_links
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


def _records_by_patterns(
    database: Database,
    patterns: List[str],
) -> List[str]:
    return [
        rec.name
        for rec in database.records.values()
        if any(
            re.search(pattern, rec.name)
            for pattern in patterns
        )
    ]


def get_database_graph(
    *loaded_items: DatabaseItem,
    highlight: Optional[List[str]] = None,
) -> RecordLinkGraph:
    """
    Get a database graph from a number of database items.
    """
    database = Database.from_multiple(*loaded_items)
    starting_records = _records_by_patterns(database, highlight) if highlight else []
    relations = build_database_relations(
        database=database.records,
        record_types=database.record_types or {},
        aliases=database.aliases or {},
    )
    return graph_links(
        database=database.records,
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
        graph = get_database_graph(*loaded_items, highlight=highlight)
    else:
        try:
            item, = loaded_items
        except ValueError:
            raise RuntimeError(
                "Sorry, multiple database files are supported but only "
                "single files for other formats."
            )

        if isinstance(item, SequencerProgram):
            graph = item.as_graph(include_code=code)
        else:
            raise RuntimeError(
                f"Sorry, graph isn't supported yet for {item.__class__.__name__}"
            )

    gv_graph = graph.to_digraph()
    logger.debug("Nodes: %s", graph.nodes)
    logger.debug("Edges: %s", graph.edges)
    render_graph_to_file(gv_graph, filename=output)
