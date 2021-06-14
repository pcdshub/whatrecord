import os
from typing import Dict

import aiohttp
import apischema

from .server.server import PVGetInfo

WHATREC_SERVER = os.environ.get(
    "WHATREC_SERVER",
    "http://localhost:8899/"
)


async def make_query(path, server=None):
    server = (server or WHATREC_SERVER).rstrip("/")

    if not path.startswith("/"):
        raise ValueError(
            "Expects path not including server, and should start with ``/``"
        )

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{server}{path}") as resp:
            return await resp.json()


async def get_record_info(*records, server=None) -> Dict[str, PVGetInfo]:
    """Get record information from the server."""
    reclist = "|".join(records)
    recordinfo = await make_query(f"/api/pv/{reclist}/info", server=server)
    return apischema.deserialize(Dict[str, PVGetInfo], recordinfo)
