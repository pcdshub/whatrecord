import pathlib

import pytest

MODULE_PATH = pathlib.Path(__file__).resolve().parent

STARTUP_SCRIPTS = list((MODULE_PATH / "iocs").glob("**/st.cmd"))


startup_scripts = pytest.mark.parametrize(
    "startup_script",
    [
        pytest.param(
            startup_script,
            id="/".join(startup_script.parts[-2:])
        )
        for startup_script in STARTUP_SCRIPTS
    ]
)
