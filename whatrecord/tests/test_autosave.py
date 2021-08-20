import pathlib
import pprint

import apischema
import pytest

from ..autosave import AutosaveRestoreFile, RestoreError, RestoreValue
from ..common import LoadContext
from . import conftest

autosave_FILES = list((conftest.MODULE_PATH / "iocs").glob("**/*.sav"))

additional_files = conftest.MODULE_PATH / "autosave_filenames.txt"
if additional_files.exists():
    for additional in open(additional_files, "rt").read().splitlines():
        autosave_FILES.append(pathlib.Path(additional))


autosave_files = pytest.mark.parametrize(
    "autosave_file",
    [
        pytest.param(
            autosave_file,
            id="/".join(autosave_file.parts[-2:])
        )
        for autosave_file in autosave_FILES
    ]
)


@autosave_files
def test_parse(autosave_file):
    proto = AutosaveRestoreFile.from_file(autosave_file)
    serialized = apischema.serialize(proto)
    pprint.pprint(serialized)
    apischema.deserialize(AutosaveRestoreFile, serialized)


def test_basic():
    result = AutosaveRestoreFile.from_string(
        """\
# save/restore V5.1	Automatically generated - DO NOT MODIFY - 130618-005710
! 5 channel(s) not connected - or not all gets were successful
XPP:R30:EVR:27:CTRL.DG0C 119
<END>
""", filename="None")
    assert result.comments == [
        "save/restore V5.1	Automatically generated - DO NOT MODIFY - 130618-005710",
    ]
    assert result.values == {
        "XPP:R30:EVR:27:CTRL": {
            "DG0C": RestoreValue(
                context=(LoadContext("None", 3), ),
                record="XPP:R30:EVR:27:CTRL",
                field="DG0C",
                pvname="XPP:R30:EVR:27:CTRL.DG0C",
                value="119",
            )
        }
    }

    assert result.errors == [
        RestoreError(
            context=(LoadContext("None", 2), ),
            number=5,
            description="channel(s) not connected - or not all gets were successful",
        )
    ]


def test_basic_array():
    result = AutosaveRestoreFile.from_string(
        '''\
# save/restore V5.1	Automatically generated - DO NOT MODIFY - 130618-005710
! 5 channel(s) not connected - or not all gets were successful
XPP:R30:EVR:27:CTRL.DG0C @array@ { "500" "0.6" "0" "0" "0" "0" "0" "0" "0"'''
        + ''' "0" "0" "0" "0" "0" "0" "0" "0" "0" "0" "0" "0" "0" "0" "0" "0" }
<END>
''', filename="None"
    )
    assert result.comments == [
        "save/restore V5.1	Automatically generated - DO NOT MODIFY - 130618-005710",
    ]
    assert result.values == {
        "XPP:R30:EVR:27:CTRL": {
            "DG0C": RestoreValue(
                context=(LoadContext("None", 3), ),
                record="XPP:R30:EVR:27:CTRL",
                field="DG0C",
                pvname="XPP:R30:EVR:27:CTRL.DG0C",
                value=[
                    "500", "0.6", "0", "0", "0", "0", "0", "0", "0", "0", "0",
                    "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0",
                    "0", "0"
                ]
            )
        }
    }

    assert result.errors == [
        RestoreError(
            context=(LoadContext("None", 2), ),
            number=5,
            description="channel(s) not connected - or not all gets were successful",
        )
    ]


def test_basic_empty_value():
    result = AutosaveRestoreFile.from_string(
        """XPP:R30:EVR:27:CTRL.DG0C \n<END>""", filename="None"
    )
    assert result.values == {
        "XPP:R30:EVR:27:CTRL": {
            "DG0C": RestoreValue(
                context=(LoadContext("None", 1), ),
                record="XPP:R30:EVR:27:CTRL",
                field="DG0C",
                pvname="XPP:R30:EVR:27:CTRL.DG0C",
                value="",
            )
        }
    }


def test_basic_string():
    result = AutosaveRestoreFile.from_string(
        r"""
XPP:R30:EVR:27:CTRL.DG0C "a quoted string"
<END>
""", filename="None"
    )
    assert result.values == {
        "XPP:R30:EVR:27:CTRL": {
            "DG0C": RestoreValue(
                context=(LoadContext("None", 2),),
                record="XPP:R30:EVR:27:CTRL",
                field="DG0C",
                pvname="XPP:R30:EVR:27:CTRL.DG0C",
                value="a quoted string",
            )
        }
    }


def test_basic_escaped():
    result = AutosaveRestoreFile.from_string(
        r"""
CTRL.DG0C a \"quoted\" string
CTRL.DG1C @array@ { "1.23" " 2.34" " 3.45" }
CTRL.DG2C @array@ { "abc" "de\"f" "g{hi\"" "jkl mno} pqr" }
<END>
""", filename="None")
    assert result.values == {
        "CTRL": {
            "DG0C": RestoreValue(
                context=(LoadContext("None", 2), ),
                record="CTRL",
                field="DG0C",
                pvname="CTRL.DG0C",
                value='a "quoted" string',
            ),
            "DG1C": RestoreValue(
                context=(LoadContext("None", 3), ),
                record="CTRL",
                field="DG1C",
                pvname="CTRL.DG1C",
                value=["1.23", " 2.34", " 3.45"],
            ),
            "DG2C": RestoreValue(
                context=(LoadContext("None", 4), ),
                record="CTRL",
                field="DG2C",
                pvname="CTRL.DG2C",
                value=["abc", 'de"f', 'g{hi"', "jkl mno} pqr"],
            ),
        }
    }


def test_basic_disconnected():
    result = AutosaveRestoreFile.from_string(
        r"""
XPP:R30:EVR:27:CTRL.DG0C a \"quoted\" string
#abc Search Issued
#def Search Issued
XPP:R30:EVR:27:CTRL.DG1C an unquoted string
#ghi Search Issued
<END>
""")
    assert result.disconnected == [
        "abc",
        "def",
        "ghi",
    ]
