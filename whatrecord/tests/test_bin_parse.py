"""Smoke tests to see if the provided IOCs load without crashing."""

import apischema
import pytest

from ..bin.parse import main, parse
from ..shell import LoadedIoc
from . import conftest

empty_db_iocs = {"fake_ad", }


@conftest.startup_scripts
def test_load_smoke(startup_script):
    loaded_ioc: LoadedIoc = parse(startup_script)
    if startup_script.parent.name not in empty_db_iocs:
        assert loaded_ioc.shell_state.database
        assert loaded_ioc.shell_state.database_definition


@conftest.startup_scripts
def test_load_round_trip_smoke(startup_script):
    loaded_ioc = parse(startup_script)
    apischema.deserialize(LoadedIoc, apischema.serialize(loaded_ioc))

    assert loaded_ioc.metadata.is_up_to_date()
    # assert loaded_ioc == round_tripped


@conftest.startup_scripts
@pytest.mark.parametrize(
    "as_json",
    [
        pytest.param(False, id="formatted"),
        pytest.param(True, id="json"),
    ]
)
def test_load_dump(startup_script, as_json):
    main(startup_script, as_json=as_json)
