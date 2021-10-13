"""
LDAP Configuration summary plugin
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import typing
from dataclasses import dataclass
from typing import Dict, List

import apischema
import ldap

from ..server.common import PluginResults

# from .util import suppress_output_decorator

logger = logging.getLogger(__name__)

# Stash the description for later usage by the CLI interface.
DESCRIPTION = __doc__.strip()

# LDAP base
# dc = Domain Component (reg)
# o = Organization (slac)
# ou = Organization unit (Subnets)
LDAP_BASE = os.environ.get("WHATRECORD_LDAP_BASE", "ou=Subnets,dc=reg,o=slac")

# LDAP scope (subtree, base, onelevel) - this probably remains as-is
LDAP_SCOPE = os.environ.get("WHATRECORD_LDAP_SCOPE", "subtree")

# LDAP filter
LDAP_FILTER = os.environ.get("WHATRECORD_LDAP_FILTER", "cn=*")

# The LDAP server URI
LDAP_SERVER = os.environ.get("WHATRECORD_LDAP_SERVER", "ldap://psldap1.pcdsn/")

# The LDAP byte encoding
LDAP_ENCODING = os.environ.get("WHATRECORD_LDAP_ENCODING", "utf-8")


@dataclass
class NetconfigPluginResults(PluginResults):
    # Could potentially further specify metadata_by_key or metadata
    ...


def decode_ldap_attrs(
    attrs: Dict[str, List[bytes]], encoding=LDAP_ENCODING
) -> Dict[str, List[str]]:
    """Decode byte-filled LDAP attrs dictionary."""
    def decode_value(key: str, value: List[bytes]):
        return [part.decode(encoding, "replace") for part in value]

    return {key: decode_value(key, value) for key, value in attrs.items()}


def main(
    server: str = LDAP_SERVER,
    base: str = LDAP_BASE,
    scope: int = ldap.SCOPE_SUBTREE,
    filter_query: str = LDAP_FILTER,
    encoding: str = LDAP_ENCODING,
    pretty: bool = False,
):
    client = ldap.initialize(server)
    metadata = {}
    for dn, attrs in client.search_s(base, scope, filter_query):
        info = decode_ldap_attrs(attrs, encoding=encoding)
        for cn in info["cn"]:
            cn_info = metadata.setdefault(cn, {})
            for key, value in info.items():
                cn_info.setdefault(key, []).extend(value)
            for dninfo in ldap.dn.str2dn(dn):
                for key, value, *_ in dninfo:
                    cn_info.setdefault(key, []).append(value)

    return NetconfigPluginResults(
        files_to_monitor={},
        record_to_metadata_keys={},
        metadata=metadata,
        metadata_by_key={},
        execution_info={},
    )


def _get_argparser(
    parser: typing.Optional[argparse.ArgumentParser] = None,
) -> argparse.ArgumentParser:
    if parser is None:
        parser = argparse.ArgumentParser(description=DESCRIPTION)

    parser.add_argument(
        "--server",
        type=str,
        help="LDAP server URI",
        default=LDAP_SERVER,
    )

    parser.add_argument(
        "--base",
        type=str,
        help="LDAP base",
        default=LDAP_BASE,
    )

    parser.add_argument(
        "--scope",
        type=str,
        help="LDAP scope",
        choices=("subtree", "base", "onelevel"),
        default=LDAP_SCOPE,
    )

    parser.add_argument(
        "--filter",
        type=str,
        dest="filter_query",
        help="LDAP filter / search query",
        default=LDAP_FILTER,
    )

    parser.add_argument(
        "--encoding",
        type=str,
        help="LDAP string encoding",
        default=LDAP_ENCODING,
    )

    parser.add_argument(
        "-p", "--pretty", action="store_true", help="Pretty JSON output"
    )
    return parser


def _cli_main():
    parser = _get_argparser()
    kwargs = vars(parser.parse_args())
    kwargs["scope"] = {
        "subtree": ldap.SCOPE_SUBTREE,
        "base": ldap.SCOPE_BASE,
        "onelevel": ldap.SCOPE_ONELEVEL,
    }[kwargs["scope"]]
    results = main(**kwargs)
    json_results = apischema.serialize(results)
    dump_args = {"indent": 4} if kwargs["pretty"] else {}
    print(json.dumps(json_results, sort_keys=True, **dump_args))


if __name__ == "__main__":
    _cli_main()
