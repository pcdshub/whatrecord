from typing import Dict, Optional

import aiohttp
import apischema

from . import settings
from .server.server import IocGetMatchesResponse, PVGetInfo


async def make_query(path, server=None, params: Optional[Dict[str, str]] = None):
    params = params or {}
    server = (server or settings.WHATREC_SERVER).rstrip("/")

    if not path.startswith("/"):
        raise ValueError(
            "Expects path not including server, and should start with ``/``"
        )

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{server}{path}") as resp:
            if resp.status != 200:
                raise RuntimeError(f"Server error: {resp.status}")
            return await resp.json()


async def get_record_info(*records, server: Optional[str] = None) -> Dict[str, PVGetInfo]:
    """Get record information from the server."""
    reclist = "|".join(records)
    response = await make_query(f"/api/pv/{reclist}/info", server=server)
    return apischema.deserialize(Dict[str, PVGetInfo], response)


async def get_iocs(
    pattern: str = "*", server: Optional[str] = None, regex: bool = False
) -> IocGetMatchesResponse:
    """Get record information from the server."""
    response = await make_query(
        f"/api/iocs/{pattern}/matches", server=server, params=dict(regex=str(regex))
    )
    return apischema.deserialize(IocGetMatchesResponse, response)
