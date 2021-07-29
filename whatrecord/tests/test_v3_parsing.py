"""V3 database parsing tests."""

import apischema
import pytest

from .. import Database
from ..common import LoadContext
from ..db import (DatabaseMenu, LinterResults, LinterWarning, RecordField,
                  RecordInstance, RecordType, RecordTypeField)

v3_or_v4 = pytest.mark.parametrize("version", [3, 4])


def test_simple():
    db = Database.from_string(
        """\
record(ai, "rec:X") {
    field(A, "test")
    field(B, test)
}
""",
        version=3
    )
    assert db.records["rec:X"] == RecordInstance(
        context=(LoadContext("None", 1), ),
        record_type="ai",
        name="rec:X",
        is_pva=False,
        fields={
            "A": RecordField(
                context=(LoadContext("None", 2), ),
                name="A",
                dtype="",
                value="test",
            ),
            "B": RecordField(
                context=(LoadContext("None", 3), ),
                name="B",
                dtype="",
                value="test",
            ),
        }
    )
    apischema.deserialize(Database, apischema.serialize(db))


def test_tab_in_field():
    db = Database.from_string(
        """\
record(ai, "rec:X") {
    field(A, "test\tvalue")
}
""",
        version=3
    )
    assert db.records["rec:X"] == RecordInstance(
        context=(LoadContext("None", 1), ),
        record_type="ai",
        name="rec:X",
        is_pva=False,
        fields={
            "A": RecordField(
                context=(LoadContext("None", 2), ),
                name="A",
                dtype="",
                value="test\tvalue",
            ),
        }
    )
    apischema.deserialize(Database, apischema.serialize(db))


@v3_or_v4
def test_breaktable(version):
    db = Database.from_string(
        """\
        breaktable(typeAttenLength) {
0.8      0.18
0.9      0.25
8.0    150.13
8.5    174.81
9.0    204.32
}
""",
        version=version
    )
    assert db.breaktables["typeAttenLength"] == (
        '0.8', '0.18', '0.9', '0.25', '8.0', '150.13', '8.5', '174.81', '9.0',
        '204.32'
    )
    apischema.deserialize(Database, apischema.serialize(db))


@v3_or_v4
def test_dbd_recordtype(version):
    db = Database.from_string(
        """\
recordtype(stringin) {
    field(NAME, DBF_STRING) {
        size(61)
        special(SPC_NOMOD)
        prompt("Record Name")
    }
    field(PINI, DBF_MENU) {
        menu(menuPini)
        interest(1)
        promptgroup("20 - Scan")
        prompt("Process at iocInit")
    }
}
""",
        version=version
    )
    assert db.record_types["stringin"] == RecordType(
        context=(LoadContext("None", 1), ),
        name="stringin",
        cdefs=[],
        fields={
            "NAME": RecordTypeField(
                context=(LoadContext("None", 2), ),
                name="NAME",
                type="DBF_STRING",
                special="SPC_NOMOD",
                prompt="Record Name",
                size="61",
                body={},
            ),
            "PINI": RecordTypeField(
                context=(LoadContext("None", 7), ),
                name="PINI",
                type="DBF_MENU",
                menu="menuPini",
                interest="1",
                promptgroup="20 - Scan",
                prompt="Process at iocInit",
                body={},
            ),
        }
    )
    apischema.deserialize(Database, apischema.serialize(db))


@v3_or_v4
def test_dbd_menus(version):
    db = Database.from_string(
        """\
menu(stringoutPOST) {
    choice(stringoutPOST_OnChange, "On Change")
    choice(stringoutPOST_Always, "Always")
}
menu(menuScan) {
    choice(menuScanPassive, "Passive")
    choice(menuScanEvent, "Event")
    choice(menuScanI_O_Intr, "I/O Intr")
    choice(menuScan10_second, "10 second")
    choice(menuScan5_second, "5 second")
    choice(menuScan2_second, "2 second")
    choice(menuScan1_second, "1 second")
    choice(menuScan_5_second, ".5 second")
    choice(menuScan_2_second, ".2 second")
    choice(menuScan_1_second, ".1 second")
}
""",
        version=version
    )
    assert db.menus["stringoutPOST"] == DatabaseMenu(
        context=(LoadContext("None", 1), ),
        name="stringoutPOST",
        choices={
            "stringoutPOST_OnChange": "On Change",
            "stringoutPOST_Always": "Always",
        },
    )

    assert db.menus["menuScan"] == DatabaseMenu(
        context=(LoadContext("None", 5), ),
        name="menuScan",
        choices={
            "menuScanPassive": "Passive",
            "menuScanEvent": "Event",
            "menuScanI_O_Intr": "I/O Intr",
            "menuScan10_second": "10 second",
            "menuScan5_second": "5 second",
            "menuScan2_second": "2 second",
            "menuScan1_second": "1 second",
            "menuScan_5_second": ".5 second",
            "menuScan_2_second": ".2 second",
            "menuScan_1_second": ".1 second",
        },
    )
    apischema.deserialize(Database, apischema.serialize(db))


@v3_or_v4
def test_dbd_cdef(version):
    db = Database.from_string(
        """\
recordtype(stringin) {
    %#include "test.h"
    %#include "test1.h"
    %#include "test2.h"
}
""",
        version=version
    )
    assert db.record_types["stringin"] == RecordType(
        context=(LoadContext("None", 1), ),
        name="stringin",
        cdefs=[
            '#include "test.h"',
            '#include "test1.h"',
            '#include "test2.h"',
        ],
        fields={},
    )
    apischema.deserialize(Database, apischema.serialize(db))


def test_alias_and_standalone_alias():
    db = Database.from_string(
        """\
record(ai, "rec:X") {
    alias("rec:Y")
    field(A, "test")
    field(B, test)
}
alias("rec:X", "rec:Z")
""",
        version=3
    )
    assert db.aliases["rec:Y"] == "rec:X"
    assert db.aliases["rec:Z"] == "rec:X"
    assert db.standalone_aliases["rec:Z"] == "rec:X"
    assert db.records["rec:X"] == RecordInstance(
        context=(LoadContext("None", 1), ),
        record_type="ai",
        name="rec:X",
        is_pva=False,
        aliases=["rec:Y", "rec:Z"],
        fields={
            "A": RecordField(
                context=(LoadContext("None", 3), ),
                name="A",
                dtype="",
                value="test",
            ),
            "B": RecordField(
                context=(LoadContext("None", 4), ),
                name="B",
                dtype="",
                value="test",
            ),
        }
    )
    apischema.deserialize(Database, apischema.serialize(db))


def test_standalone_alias():
    db = Database.from_string(
        """\
record(ai, "rec:X") {
    field(A, "test")
    field(B, test)
}
alias("rec:X", "rec:Y")
""",
        version=3
    )
    assert db.records["rec:X"] == RecordInstance(
        context=(LoadContext("None", 1), ),
        record_type="ai",
        name="rec:X",
        is_pva=False,
        aliases=["rec:Y"],
        fields={
            "A": RecordField(
                context=(LoadContext("None", 2), ),
                name="A",
                dtype="",
                value="test",
            ),
            "B": RecordField(
                context=(LoadContext("None", 3), ),
                name="B",
                dtype="",
                value="test",
            ),
        }
    )
    apischema.deserialize(Database, apischema.serialize(db))


def test_unquoted_warning():
    lint = LinterResults.from_database_string(
        """\
record(ai, "rec:X") {
    field(A, "test")
    field(B, test)
}
""",
        version=3
    )
    assert lint.warnings == [
        LinterWarning(
            name="unquoted_field",
            line=3,
            message="Unquoted field value 'B'"
        )
    ]
