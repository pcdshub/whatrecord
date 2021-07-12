"""
"whatrecord info" is used to get PV information from the whatrecord server.
"""

import argparse
import json
import logging
import sys

import apischema

from ..client import get_record_info
from ..format import FormatContext

logger = logging.getLogger(__name__)
DESCRIPTION = __doc__


def build_arg_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    parser.description = DESCRIPTION
    parser.formatter_class = argparse.RawTextHelpFormatter

    parser.add_argument(
        "records", type=str, nargs="+", help="Record name(s)"
    )

    parser.add_argument(
        "--json", dest="as_json", action="store_true", help="Output raw JSON"
    )
    return parser


async def main(records, as_json=False, file=sys.stdout):
    info = await get_record_info(*records)
    if as_json:
        # TODO: JSON -> obj -> JSON round tripping
        json_info = apischema.serialize(info)
        print(json.dumps(json_info, indent=4))
    else:
        fmt = FormatContext()
        for pv, pv_get_info in info.items():
            print(pv, file=file)
            print("-" * len(pv), file=file)
            print(file=file)
            print(fmt.render_object(pv_get_info, "console"), file=file)
