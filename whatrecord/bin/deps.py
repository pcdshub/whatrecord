"""
"whatrecord info" is used to get PV information from the whatrecord server.
"""

import argparse
import json
import logging
import sys
from typing import Optional

import apischema

from ..common import AnyPath
from ..format import FormatContext
from ..makefile import DependencyGroup, DependencyGroupGraph, Makefile
from .graph import render_graph_to_file

logger = logging.getLogger(__name__)
DESCRIPTION = __doc__


def build_arg_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    parser.description = DESCRIPTION
    parser.formatter_class = argparse.RawTextHelpFormatter

    parser.add_argument(
        "path", type=str, help="Path to IOC or Makefile itself"
    )

    parser.add_argument(
        "--keep-os-env",
        action="store_true",
        help=(
            "Keep environment variables present outside of ``make`` in the "
            ".env dictionaries"
        )
    )

    parser.add_argument(
        "--no-recurse",
        action="store_true",
        help="Do not recurse into dependencies",
    )

    parser.add_argument(
        "--friendly",
        dest="friendly",
        action="store_true",
        help="Output user-friendly text instead of JSON",
    )

    parser.add_argument(
        "--graph",
        action="store_true",
        help="Output a graph of dependencies",
    )

    parser.add_argument(
        "-o", "--graph-output",
        type=str,
        required=False,
        help="Output file to write to.  Defaults to standard output.",
    )

    return parser


def main(
    path: AnyPath,
    friendly: bool = False,
    no_recurse: bool = False,
    keep_os_env: bool = False,
    graph: bool = False,
    graph_output: Optional[str] = None,
    file=sys.stdout,
):
    makefile_path = Makefile.find_makefile(path)
    makefile = Makefile.from_file(makefile_path, keep_os_env=keep_os_env)
    info = DependencyGroup.from_makefile(
        makefile, recurse=not no_recurse, keep_os_env=keep_os_env
    )

    if graph:
        group_graph = DependencyGroupGraph(info)
        render_graph_to_file(group_graph.to_digraph(), filename=graph_output)
        # An alternative to 'whatrecord graph'; both should have the same
        # result in the end.
        return

    if not friendly:
        json_info = apischema.serialize(info)
        print(json.dumps(json_info, indent=4))
    else:
        fmt = FormatContext()
        print(fmt.render_object(info, "console"), file=file)
