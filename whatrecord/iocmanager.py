"""
SLAC PCDS IocManager configuration file loading support.
"""

import ast
import logging
import os
import pathlib
import re
from typing import Any, Callable, List, Optional, Union

from .common import IocInfoDict
from .util import find_binary_from_hashbang

logger = logging.getLogger(__name__)

KEY_RE = re.compile(r"([a-z_]+)\s*:", re.IGNORECASE)
EPICS_SITE_TOP = os.environ.get("EPICS_SITE_TOP", "/reg/g/pcds/epics")
REQUIRED_KEYS = {"id", "host", "port", "dir", "base_version"}


def validate_config_keys(cfg: IocInfoDict) -> bool:
    """Validate that a configuration has all required keys."""
    return all(key in cfg and cfg[key] for key in REQUIRED_KEYS)


def parse_config(lines: List[str]) -> List[IocInfoDict]:
    """
    Parse an IOC manager config to get its IOCs.

    Parameters
    ----------
    lines : list of str
        List of raw configuration file lines.

    Returns
    -------
    ioc_info : list of IOC info dictionaries
        List of IOC info
    """
    entries = []
    loading = False
    entry = None

    for line in lines:
        if "procmgr_config" in line:
            loading = True
            continue
        if not loading:
            continue
        if "id:" in line:
            if "}" in line:
                entries.append(line)
            else:
                entry = line
        elif entry is not None:
            entry += line
            if "}" in entry:
                entries.append(entry)
                entry = None

    def fix_entry(entry):
        return ast.literal_eval(KEY_RE.sub(r'"\1":', entry.strip(", \t")))

    result = []
    for entry in entries:
        try:
            result.append(fix_entry(entry))
        except Exception:
            logger.exception("Failed to fix up IOC manager entry: %s", entry)

    return result


def load_config_file(fn: Union[str, pathlib.Path]) -> List[IocInfoDict]:
    """
    Load a configuration file and return the IOCs it contains.

    Parameters
    ----------
    fn : str or pathlib.Path
        The configuration filename

    Returns
    -------
    ioc_info : list of IOC info dictionaries
        List of IOC info
    """
    with open(fn, "rt") as f:
        lines = f.read().splitlines()

    iocs = parse_config(lines)

    for ioc in list(iocs):
        # For now, assume old database syntax by specifying 3.15:
        ioc["base_version"] = "3.15"
        if not validate_config_keys(ioc):
            iocs.remove(ioc)
        else:
            # Add "config_file" and rename some keys:
            ioc["config_file"] = str(fn)
            ioc["name"] = ioc.pop("id")
            ioc["script"] = find_stcmd(ioc["dir"], ioc["name"])
            ioc["binary"] = find_binary_from_hashbang(ioc["script"])

    return iocs


def find_stcmd(directory: str, ioc_id: str) -> str:
    """Find the startup script st.cmd for a given IOC."""
    if directory.startswith("ioc"):
        directory = os.path.join(EPICS_SITE_TOP, directory)

    suffix = ("iocBoot", ioc_id, "st.cmd")
    # Templated IOCs are... different:
    options = [
        os.path.join(directory, "children", "build", *suffix),
        os.path.join(directory, "build", *suffix),
        os.path.join(directory, *suffix),
        os.path.join(directory, "st.cmd"),
    ]

    for option in options:
        if os.path.exists(option):
            return option

    # Guess at what's correct:
    return options[-1]


def get_iocs_from_configs(
    configs: List[Union[str, pathlib.Path]],
    sorter: Optional[Callable[[IocInfoDict], Any]] = None
) -> List[IocInfoDict]:
    """
    Get IOC information in a list of dictionaries.

    Parameters
    ----------
    configs : list[str or pathlib.Path]
        Configuration filenames to load.
    sorter : callable, optional
        Sort IOCs with this, defaults to sorting by host name and then IOC name.

    Returns
    -------
    ioc_info : list of IOC info dictionaries
        List of IOC info
    """
    configs = [
        pathlib.Path(config).resolve()
        for config in configs or []
    ]

    def default_sorter(ioc):
        return (ioc["host"], ioc["name"])

    iocs = (
        ioc
        for fn in set(configs)
        for ioc in load_config_file(fn)
    )

    return list(sorted(iocs, key=sorter or default_sorter))
