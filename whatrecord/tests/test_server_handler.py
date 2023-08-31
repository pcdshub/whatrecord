"""Requires pytest-aiohttp"""
import json
import logging
from typing import (Any, Awaitable, Callable, Dict, Generator, Optional, Type,
                    TypeVar, Union)

import aiohttp
import aiohttp.test_utils
import aiohttp.web
import apischema
import pytest
import pytest_asyncio
from aiohttp.test_utils import BaseTestServer, TestClient, TestServer
from aiohttp.web import Application

from .. import gateway
from ..common import RecordInstance, WhatRecord
from ..server.server import (IocGetDuplicatesResponse, IocGetMatchesResponse,
                             IocGetMatchingRecordsResponse, PVGetInfo,
                             PVGetMatchesResponse, ServerHandler, ServerState,
                             _new_server)
from .conftest import MODULE_PATH, STARTUP_SCRIPTS

logger = logging.getLogger(__name__)

from .test_server_state import ready_state, state  # noqa

AiohttpClient = Callable[[Union[Application, BaseTestServer]], Awaitable[TestClient]]


@pytest.fixture()
def handler(ready_state: ServerState) -> ServerHandler:   # noqa: F811
    return ServerHandler(ready_state)


@pytest.fixture()
def server(handler: ServerHandler) -> aiohttp.web.Application:
    app = _new_server(handler, port=58433, run=False)
    # Don't do the initialization steps; we already have initialized enough
    # for the purposes of testing
    app.on_startup.remove(handler.async_init)
    return app


@pytest_asyncio.fixture
async def aiohttp_client() -> Generator[AiohttpClient, None, None]:
    """
    Factory to create a TestClient instance.

    Borrowed and modified from pytest-aiohttp, as a recent version is
    unavailable on conda-forge for our testing purposes.

    aiohttp_client(app, **kwargs)
    aiohttp_client(server, **kwargs)
    aiohttp_client(raw_server, **kwargs)
    """
    clients = []

    async def go(
        __param: Union[Application, BaseTestServer],
        *,
        server_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> TestClient:
        if isinstance(__param, Application):
            server_kwargs = server_kwargs or {}
            server = TestServer(__param, **server_kwargs)
            client = TestClient(server, **kwargs)
        elif isinstance(__param, BaseTestServer):
            client = TestClient(__param, **kwargs)
        else:
            raise ValueError(f"Unknown argument type: {type(__param)}")

        await client.start_server()
        clients.append(client)
        return client

    yield go

    while clients:
        await clients.pop().close()


@pytest_asyncio.fixture()
async def client(server: aiohttp.web.Application, aiohttp_client):
    return await aiohttp_client(server)


pvname = "IOC:KFE:A:One"
nonexistent_pvname = "pleasedonotmatch"
T = TypeVar("T")


async def get_response(
    client: aiohttp.web.Application,
    url: str,
    params: Optional[Dict[str, str]] = None
) -> aiohttp.ClientResponse:
    logger.debug("Request: %s (params=%s)", url, params)
    resp = await client.get(url, params=params or {})
    assert resp.status == 200
    return resp


async def get_json(
    client: aiohttp.web.Application, url: str,
    params: Optional[Dict[str, str]] = None
) -> dict:
    resp = await get_response(client, url, params)
    data = json.loads(await resp.text())
    logger.debug("Received: %s", data)
    return data


async def get_and_deserialize(
    client: aiohttp.web.Application, url: str, cls: Type[T],
    params: Optional[Dict[str, str]] = None
) -> T:
    data = await get_json(client, url, params)
    return apischema.deserialize(cls, data)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url, cls, params, expected",
    [
        pytest.param(
            "/api/pv/matches",
            PVGetMatchesResponse,
            dict(pattern=f"{pvname}.*", regex="true"),
            PVGetMatchesResponse(
                patterns=[pvname + ".*"],
                regex=True,
                matches=[pvname],
            ),
            id="match-regex"
        ),
        pytest.param(
            "/api/pv/matches",
            PVGetMatchesResponse,
            dict(pattern=f"{pvname}*", regex="false"),
            PVGetMatchesResponse(
                patterns=[pvname + "*"],
                regex=False,
                matches=[pvname],
            ),
            id="match-glob"
        ),
        pytest.param(
            "/api/ioc/pvs",
            IocGetMatchingRecordsResponse,
            dict(ioc="*", pv=nonexistent_pvname, regex="False"),
            IocGetMatchingRecordsResponse(
                ioc_patterns=["*"],
                record_patterns=[nonexistent_pvname],
                regex=False,
                matches=[],
            ),
            id="ioc-no-matching-records-glob"
        ),
        pytest.param(
            "/api/ioc/pvs",
            IocGetMatchingRecordsResponse,
            dict(ioc=".*", pv=nonexistent_pvname, regex="true"),
            IocGetMatchingRecordsResponse(
                ioc_patterns=[".*"],
                record_patterns=[nonexistent_pvname],
                regex=True,
                matches=[],
            ),
            id="ioc-no-matching-records-regex"
        ),
    ],
)
async def test_request(
    client,
    server: aiohttp.web.Application,
    url: str,
    cls: Type[T],
    params: Dict[str, str],
    expected: T,
):
    response = await get_and_deserialize(
        client,
        url=url,
        cls=cls,
        params=params,
    )
    assert response == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url, params",
    [
        pytest.param(
            "/api/ioc/pvs",
            dict(ioc="*", pv="*", regex="false"),
            id="match-glob"
        ),
        pytest.param(
            "/api/ioc/pvs",
            dict(ioc=".*", pv=".*", regex="true"),
            id="match-regex"
        ),
        pytest.param(
            "/api/file/info",
            dict(file=str(STARTUP_SCRIPTS[0])),
            id="file-info"
        ),
        pytest.param(
            "/api/logs/get",
            dict(),
            id="logs"
        ),
        pytest.param(
            "/api/pv/info",
            dict(pv=pvname),
            id="pv-info"
        ),
        pytest.param(
            "/api/pv/relations",
            dict(pv=pvname),
            id="relations"
        ),
        # No plugin info
        # pytest.param(
        #     "/api/plugin/info",
        #     dict(),
        #     id="plugin-info"
        # ),
    ],
)
async def test_request_smoke(
    client, server: aiohttp.web.Application,
    url: str,
    params: Dict[str, str],
):
    response = await get_json(
        client,
        url=url,
        params=params,
    )
    assert len(response)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url, params",
    [
        pytest.param(
            "/api/pv/graph",
            dict(pv=pvname, format="dot"),
            id="pv-dot"
        ),
        pytest.param(
            "/api/pv/script-graph",
            dict(pv=pvname, format="dot"),
            id="script-dot"
        ),
    ],
)
async def test_graph_smoke(
    client,
    server: aiohttp.web.Application,
    url: str,
    params: Dict[str, str],
):
    response = await get_response(
        client,
        url=url,
        params=params,
    )
    data = await response.text()
    assert "digraph" in data
    assert len(data)


@pytest.mark.parametrize(
    "pvname, key, value",
    [
        pytest.param(
            pvname,
            "gateway",
            {
                "name": "IOC:KFE:A:One",
                "matches": [
                    {
                        "filename": str(MODULE_PATH / "kfe.pvlist"),
                        "rule": {
                            "context": [
                                [
                                    str(MODULE_PATH / "kfe.pvlist"),
                                    10,
                                ]
                            ],
                            "pattern": "[A-Z][A-Z][A-Z]:KFE:.*",
                            "command": "ALLOW",
                            "header": "",
                            "metadata": {},
                        },
                        "groups": [],
                    }
                ],
            },
            id="gateway"
        ),
    ],
)
@pytest.mark.asyncio
async def test_record_metadata(
    client, server: aiohttp.web.Application,
    pvname: str,
    key: str,
    value: Any
):
    response = await get_and_deserialize(
        client,
        url="/api/pv/info",
        params=dict(pv=pvname),
        cls=Dict[str, PVGetInfo],
    )
    pv_get_info = response[pvname]
    assert pv_get_info.pv_name == pvname
    assert pv_get_info.present
    assert len(pv_get_info.info) == 1

    # Wow, does this really need to be so nested?!
    whatrec: WhatRecord = pv_get_info.info[0]
    instance: RecordInstance = whatrec.record.instance
    assert instance.metadata[key] == value


@pytest.mark.parametrize(
    "regex",
    [True, False]
)
@pytest.mark.asyncio
async def test_get_duplicates(
    client, server: aiohttp.web.Application, regex: bool
):
    response = await get_and_deserialize(
        client,
        url="/api/pv/duplicates",
        params=dict(regex=str(regex)),
        cls=IocGetDuplicatesResponse,
    )
    assert response == IocGetDuplicatesResponse(
        patterns=[".*" if regex else "*"],
        regex=regex,
        duplicates={"IOC:KFE:C:One": ["ioc_c", "ioc_d"]},
    )


@pytest.mark.asyncio
async def test_get_matches(
    client, server: aiohttp.web.Application,
):
    response = await get_and_deserialize(
        client,
        url="/api/ioc/matches",
        params=dict(pattern="ioc_[cd]$", regex="true"),
        cls=IocGetMatchesResponse,
    )
    assert response.patterns == ["ioc_[cd]$"]
    assert response.regex
    assert len(response.matches) == 2
    assert response.matches[0].name == "ioc_c"
    assert response.matches[1].name == "ioc_d"


@pytest.mark.asyncio
async def test_gateway_info(
    client, server: aiohttp.web.Application,
):
    info = await get_and_deserialize(
        client,
        url="/api/gateway/info",
        params=dict(),
        cls=gateway.GatewayConfig,
    )

    filename, kfe_pvlist = list(info.pvlists.items())[0]
    assert filename.name == "kfe.pvlist"
    assert kfe_pvlist.evaluation_order == "ALLOW, DENY"


# TODO: any way of testing plugin/nested/{info,keys}?
