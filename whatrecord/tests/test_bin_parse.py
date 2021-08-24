"""Smoke tests to see if the provided IOCs load without crashing."""

import os

import apischema
import pytest

from ..bin.parse import main, parse
from ..shell import LoadedIoc, ShellState
from . import conftest

empty_db_iocs = {"fake_ad", }


@conftest.startup_scripts
def test_load_smoke(startup_script):
    os.environ["PWD"] = str(startup_script.resolve().parent)
    loaded_ioc: LoadedIoc = parse(startup_script)
    if startup_script.parent.name not in empty_db_iocs:
        assert loaded_ioc.shell_state.database
        assert loaded_ioc.shell_state.database_definition


@conftest.startup_scripts
def test_load_round_trip_smoke(startup_script):
    os.environ["PWD"] = str(startup_script.resolve().parent)
    loaded_ioc = parse(startup_script)
    apischema.deserialize(LoadedIoc, apischema.serialize(loaded_ioc))

    assert loaded_ioc.metadata.is_up_to_date()
    # assert loaded_ioc == round_tripped


@conftest.startup_scripts
def test_load_and_whatrec(startup_script):
    os.environ["PWD"] = str(startup_script.resolve().parent)
    loaded_ioc: LoadedIoc = parse(startup_script)
    state: ShellState = loaded_ioc.shell_state

    v3_db = state.database
    if v3_db:
        pvname = list(v3_db)[0]
        whatrec = loaded_ioc.whatrec(pvname)
        assert whatrec is not None

        rec = whatrec.record.instance
        dbd = whatrec.record.definition
        assert whatrec.name == rec.name == pvname
        assert rec == state.database[pvname]
        if rec.record_type != "motor":  # sorry, dbd doesn't have it
            assert dbd == state.database_definition.record_types[rec.record_type]

    pva_db = state.pva_database
    if pva_db:
        pvname = list(pva_db)[0]
        whatrec = loaded_ioc.whatrec(pvname)
        assert whatrec is not None

        rec = whatrec.pva_group
        assert whatrec.name == rec.name == pvname
        assert rec == state.pva_database[pvname]


friendly_param = pytest.mark.parametrize(
    "friendly",
    [
        pytest.param(True, id="friendly"),
        pytest.param(False, id="json"),
    ]
)


@conftest.startup_scripts
@friendly_param
def test_load_dump(startup_script, friendly):
    os.environ["PWD"] = str(startup_script.resolve().parent)
    main(startup_script, friendly=friendly)


@friendly_param
@pytest.mark.parametrize(
    "filename",
    [
        pytest.param(conftest.MODULE_PATH / fn, id=fn)
        for fn in [
            "access.acf",
            "kfe.pvlist",
            "iocs/db/test.substitutions",
            "iocs/streamdevice/hex.proto",
        ]
    ]
)
def test_load_misc(filename, friendly):
    os.environ["PWD"] = str(filename.resolve().parent)
    main(filename, friendly=friendly)
