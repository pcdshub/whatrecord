"""
"whatrecord iocmanager-loader" is used to import IOC configuration information
from SLAC PCDS IocManager-format configuration files.
"""

import argparse
import json
import logging
from typing import List

from ..common import AnyPath, IocInfoDict
from ..iocmanager import get_iocs_from_configs

logger = logging.getLogger(__name__)
DESCRIPTION = __doc__


def build_arg_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    parser.description = DESCRIPTION
    parser.formatter_class = argparse.RawTextHelpFormatter

    parser.add_argument(
        "configs", type=str, nargs="+", help="Configuration file location(s)"
    )

    parser.add_argument(
        "--limit", type=int, default=0, help="Limit the number of IOCs to output"
    )

    return parser


def main(configs: list[AnyPath], limit: int = 0) -> List[IocInfoDict]:
    iocs = get_iocs_from_configs(configs)
    if limit:
        dumped = json.dumps(iocs[-limit:], indent=4)
    else:
        dumped = json.dumps(iocs, indent=4)

    print(dumped)
    return iocs
