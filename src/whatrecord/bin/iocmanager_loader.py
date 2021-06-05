"""
"whatrec iocmanager_loader" is used to import IOC configuration information
from SLAC PCDS IocManager-format configuration files.
"""

import argparse
import json
import logging
from typing import List

from ..common import IocMetadata
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

    return parser


def main(configs) -> List[IocMetadata]:
    iocs = get_iocs_from_configs(configs)
    print(json.dumps(iocs, indent=4))
    return iocs
