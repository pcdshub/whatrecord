"""Placeholder for V3 database parsing tests, for the most part..."""

import apischema
import pytest

from .. import Database
from ..db import DatabaseBreakTable, LoadContext, RecordField, RecordInstance

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
    assert db.breaktables["typeAttenLength"] == DatabaseBreakTable(
        name='typeAttenLength',
        values=('0.8', '0.18', '0.9', '0.25', '8.0', '150.13', '8.5', '174.81',
                '9.0', '204.32')
    )
    apischema.deserialize(Database, apischema.serialize(db))
