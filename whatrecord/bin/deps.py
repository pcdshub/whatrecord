"""
"whatrecord deps" is used to get dependency information from EPICS IOC or
module Makefiles.

Under the hood, this uses GNU make, which is an external dependency required
for correct functionality.
"""

import argparse
import logging
from typing import List, Optional

from ..common import AnyPath
from ..makefile import DependencyGroup, DependencyGroupGraph, Makefile
from ..util import write_to_file
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
        "-of", "--output-format",
        default="json",
        type=str,
        help="Output format to use (json, console, file)",
    )

    parser.add_argument(
        "--graph",
        action="store_true",
        help="Output a graph of dependencies",
    )

    parser.add_argument(
        "-d",
        "--define",
        dest="defines",
        type=str,
        nargs="*",
        help="Define a variable for GNU make in the form: VARIABLE=VALUE",
    )

    parser.add_argument(
        "-o", "--graph-output",
        type=str,
        required=False,
        help="Graph output filename.  Defaults to standard output.",
    )

    return parser


def main(
    path: AnyPath,
    no_recurse: bool = False,
    keep_os_env: bool = False,
    graph: bool = False,
    graph_output: Optional[str] = None,
    output_format: str = "json",
    defines: Optional[List[str]] = None,
):
    variables = dict(variable.split("=", 1) for variable in defines or [])
    makefile_path = Makefile.find_makefile(path)
    makefile = Makefile.from_file(
        makefile_path, keep_os_env=keep_os_env, variables=variables
    )
    info = DependencyGroup.from_makefile(
        makefile, recurse=not no_recurse, keep_os_env=keep_os_env
    )

    if graph:
        group_graph = DependencyGroupGraph(info)
        render_graph_to_file(group_graph.to_digraph(), filename=graph_output)
        # An alternative to 'whatrecord graph'; both should have the same
        # result in the end.

    if not graph or graph_output is None:
        write_to_file(info, format=output_format)
