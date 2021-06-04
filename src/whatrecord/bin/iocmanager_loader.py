"""
"whatrec iocmanager_loader" is used to import IOC lists from SLAC's IocManager
configuration files.
"""

import argparse
import ast
import json
import logging
import os
import re
from typing import Dict, List

logger = logging.getLogger(__name__)
DESCRIPTION = __doc__

KEY_RE = re.compile(r'([a-z_]+)\s*:', re.IGNORECASE)


def build_arg_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    parser.description = DESCRIPTION
    parser.formatter_class = argparse.RawTextHelpFormatter

    parser.add_argument(
        '--configs',
        type=str,
        nargs='+',
        help="Configuration file location(s)"
    )

    return parser


def parse_config(lines) -> List[Dict[str, str]]:
    """Parse an IOC manager config to get its IOCs."""
    entries = []
    loading = False
    entry = None

    for line in lines:
        if 'procmgr_config' in line:
            loading = True
            continue
        if not loading:
            continue
        if 'id:' in line:
            if '}' in line:
                entries.append(line)
            else:
                entry = line
        elif entry is not None:
            entry += line
            if '}' in entry:
                entries.append(entry)
                entry = None

    result = []
    for entry in entries:
        result.append(
            ast.literal_eval(KEY_RE.sub(r'"\1":', entry.strip(', \t')))
        )
    return result


def load_config_file(fn) -> List[Dict[str, str]]:
    """
    Load a configuration file and return the IOCs it contains.

    Parameters
    ----------
    fn : str or pathlib.Path
        The configuration filename
    """
    with open(fn, 'rt') as f:
        lines = f.read().splitlines()

    return parse_config(lines)


def find_stcmd(directory: str, ioc_id: str) -> str:
    """Find the startup script st.cmd for a given IOC."""
    if directory.startswith("ioc"):
        directory = os.path.join("/reg/g/pcds/epics", directory)

    # Templated IOCs are... different:
    build_path = os.path.join(directory, "build", "iocBoot", ioc_id)
    if os.path.exists(build_path):
        return os.path.join(build_path, "st.cmd")

    # Otherwise, it should be straightforward:
    return os.path.join(directory, "iocBoot", ioc_id, "st.cmd")


def main(configs):
    iocs = [
        ioc
        for fn in (configs or [])
        for ioc in load_config_file(fn)
    ]

    iocs.sort(key=lambda ioc: ioc.get("host", '?'))

    for ioc_info in iocs:
        directory = ioc_info.get("dir", None)
        # disable = ioc_info.get("disable", False)
        if not directory:
            continue
        ioc_id = ioc_info.get("id", None)
        stcmd = find_stcmd(directory, ioc_id)
        ioc_info["startup_script"] = stcmd
        # if os.path.exists(stcmd):
        #     ioc_info["startup_script"] = stcmd
        # elif not disable:
        #     # print("missing stcmd", stcmd, ioc_info)
        #     ...

    print(json.dumps(iocs, indent=4))
