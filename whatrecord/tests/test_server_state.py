import asyncio
import logging

import pytest

from ..server.server import ServerState, _new_server_state
from .conftest import MODULE_PATH, STARTUP_SCRIPTS

logger = logging.getLogger(__name__)


def test_init_basic():
    ServerState()


@pytest.fixture()
def state():
    return _new_server_state(
        scripts=[str(script) for script in STARTUP_SCRIPTS],
        gateway_config=str(MODULE_PATH),
    )


@pytest.fixture()
def ready_state(state: ServerState, caplog):
    caplog.set_level("INFO")
    # asyncio.run(state.async_init(app=None), debug=True)
    logger.info("Updating script loaders")
    asyncio.run(state.update_script_loaders())
    asyncio.run(state.update_iocs(state.get_updated_iocs()))
    state._load_gateway_config()
    # asyncio.run(state.update_plugins())
    return state


def test_cli_state_init(state: ServerState):
    ...


def test_misc(ready_state: ServerState):
    print(ready_state.ioc_metadata)
    assert ready_state._update_count == 1

    pvname, iocname = "IOC:KFE:A:One", "ioc_a"
    what, = ready_state.whatrec(pvname)
    assert what.record is not None
    assert what.pva_group is None
    assert what.record.instance == ready_state.database[pvname]

    script = ready_state.container.scripts[iocname]
    dbd = script.shell_state.database_definition
    assert what.record.definition == dbd.record_types[
        what.record.instance.record_type
    ]

    pvname, iocname = "PVACCESS:SIMPLE:01", "pva_simple"
    what, = ready_state.whatrec(pvname)
    assert what.record is None
    assert what.pva_group is not None
    assert what.pva_group == ready_state.pva_database[pvname]

    # script = ready_state.container.scripts[iocname]
