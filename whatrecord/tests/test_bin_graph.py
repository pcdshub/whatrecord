"""Smoke tests to see if the provided IOCs load without crashing."""

import pytest

from ..bin.graph import main
from . import conftest


@conftest.startup_scripts
def test_graph_smoke_startup_script(startup_script):
    main(filenames=[startup_script])


@pytest.mark.parametrize(
    "with_dbd", [
        pytest.param(True, id="with_dbd"),
        pytest.param(False, id="without_dbd"),
    ]
)
def test_graph_db(with_dbd):
    db_path = conftest.MODULE_PATH / "iocs" / "streamdevice" / "test.db"
    if with_dbd:
        dbd_path = str(conftest.MODULE_PATH / "iocs" / "softIoc.dbd")
    else:
        dbd_path = None
    main(filenames=[db_path], dbd=dbd_path)


@pytest.mark.parametrize(
    "with_dbd", [
        pytest.param(True, id="with_dbd"),
        pytest.param(False, id="without_dbd"),
    ]
)
def test_graph_multiple_db(with_dbd):
    db_paths = [
        conftest.MODULE_PATH / "iocs" / "streamdevice" / "test.db",
        conftest.MODULE_PATH / "iocs" / "ioc_a" / "ioc_a.db",
    ]
    if with_dbd:
        dbd_path = str(conftest.MODULE_PATH / "iocs" / "softIoc.dbd")
    else:
        dbd_path = None
    main(filenames=db_paths, dbd=dbd_path)
