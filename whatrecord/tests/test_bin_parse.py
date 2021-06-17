"""Smoke tests to see if the provided IOCs load without crashing."""

import pytest

from ..bin.parse import main, parse
from . import conftest


@conftest.startup_scripts
def test_load_smoke(startup_script):
    parse(startup_script)


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
