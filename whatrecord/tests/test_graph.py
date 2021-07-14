import pytest

from .. import graph
from ..common import LoadContext, RecordField
from ..db import Database


def create_record_def(record_type):
    return f"""
recordtype({record_type}) {{
    field(INP, DBF_INLINK) {{
    }}
    field(OUT, DBF_OUTLINK) {{
    }}
    field(VAL, DBF_STRING) {{
    }}
}}
"""


def create_record(record_type, record_name, fields, filename=None):
    filename = filename or f"{record_name}.db"
    field_source = "\n".join(
        f'field({field_name}, "{field_value}")'
        for field_name, field_value in fields.items()
    )
    db_source = create_record_def(record_type) + f"""
record({record_type}, "{record_name}") {{
    {field_source}
}}
"""
    print(f"---- {filename}:")
    for lineno, line in enumerate(db_source.splitlines(), 1):
        print(lineno, line)

    db = Database.from_string(db_source, filename=filename)
    return db.records[record_name]


def test_simple_graph():
    database = {
        "record_a": create_record("ai", "record_a", {"INP": "record_b CPP MS", "VAL": "10"}),
        "record_b": create_record("ao", "record_b", {"OUT": "record_c CA", "VAL": "20"}),
    }
    relations = graph.build_database_relations(database)
    print(database["record_a"])
    assert relations["record_a"]["record_b"] == [
        (
            database["record_a"].fields["INP"],
            database["record_b"].fields["VAL"],
            ("CPP", "MS"),
        ),
    ]
    assert relations["record_b"]["record_a"] == [
        (
            database["record_b"].fields["VAL"],
            database["record_a"].fields["INP"],
            ("CPP", "MS"),
        ),
    ]
    assert relations["record_b"]["record_c"] == [
        (
            database["record_b"].fields["OUT"],
            RecordField(
                dtype='unknown', name='VAL', value='(unknown-record)',
                context=(LoadContext("unknown", 0), ),
            ),
            ("CA", ),
        ),
    ]


@pytest.fixture
def dbd():
    return Database.from_string(
        "\n".join((
            create_record_def(rec_type)
            for rec_type in ["ai", "ao"]
        )),
        filename="the.dbd",
    )


def test_combine_relations():
    database_1 = {
        "record_a": create_record("ai", "record_a", {"INP": "record_b CPP MS", "VAL": "10"}),
        "record_b": create_record("ao", "record_b", {"OUT": "record_c CA", "VAL": "20"}),
    }
    database_2 = {
        "record_c": create_record("ao", "record_c", {"OUT": "record_d.INP", "VAL": "10"}),
        "record_d": create_record("ai", "record_d", {"INP": "", "VAL": "10"}),
        "record_e": create_record("ai", "record_e", {"INP": "record_a CP", "VAL": "10"}),
    }
    relations = graph.build_database_relations(database_1)
    graph.combine_relations(
        relations,
        database_1,
        graph.build_database_relations(database_2),
        database_2,
    )

    assert relations["record_a"]["record_b"] == [
        (
            database_1["record_a"].fields["INP"],
            database_1["record_b"].fields["VAL"],
            ("CPP", "MS"),
        ),
    ]
    assert relations["record_b"]["record_a"] == [
        (
            database_1["record_b"].fields["VAL"],
            database_1["record_a"].fields["INP"],
            ("CPP", "MS"),
        ),
    ]
    assert relations["record_b"]["record_c"] == [
        (
            database_1["record_b"].fields["OUT"],
            # RecordField(
            #     dtype='unknown', name='VAL', value='(unknown-record)',
            #     context=(LoadContext("unknown", 0), ),
            # ),
            database_2["record_c"].fields["VAL"],
            ("CA", ),
        ),
    ]
    assert relations["record_c"]["record_d"] == [
        (
            database_2["record_c"].fields["OUT"],
            database_2["record_d"].fields["INP"],
            (),
        ),
    ]
    assert relations["record_d"]["record_c"] == [
        (
            database_2["record_d"].fields["INP"],
            database_2["record_c"].fields["OUT"],
            (),
        ),
    ]
    assert relations["record_e"]["record_a"] == [
        (
            database_2["record_e"].fields["INP"],
            database_1["record_a"].fields["VAL"],
            ("CP", ),
        ),
    ]


def test_with_unset_field(dbd: Database):
    database_1 = {
        "record_a": create_record("ai", "record_a", {"INP": "record_b CPP MS", "VAL": "10"}),
        "record_b": create_record("ao", "record_b", {"OUT": "record_c CA"}),
    }
    relations = graph.build_database_relations(database_1, record_types=dbd.record_types)
    assert relations["record_a"]["record_b"] == [
        (
            database_1["record_a"].fields["INP"],
            # database_1["record_b"].fields["VAL"],  # <-- not defined, but in dbd
            RecordField(
                dtype="DBF_STRING",
                name="VAL",
                value="",
                context=(LoadContext("the.dbd", 17),),
            ),
            ("CPP", "MS"),
        ),
    ]


def test_with_invalid_field(dbd: Database):
    database_1 = {
        "record_a": create_record("ai", "record_a", {"INP": "record_b.INVAL CPP MS", "VAL": "10"}),
        "record_b": create_record("ao", "record_b", {"OUT": "record_c CA"}),
    }
    relations = graph.build_database_relations(database_1, record_types=dbd.record_types)
    assert relations["record_a"]["record_b"] == [
        (
            database_1["record_a"].fields["INP"],
            RecordField(
                dtype="invalid",
                name="INVAL",
                value="(invalid-field)",
                context=(LoadContext("unknown", 0),),
            ),
            ("CPP", "MS"),
        ),
    ]


def test_with_weird_record_type(dbd: Database):
    database_1 = {
        "record_a": create_record("ai", "record_a", {"INP": "record_b.ABC CPP MS", "VAL": "10"}),
        "record_b": create_record("aq", "record_b", {"OUT": "record_c CA"}),
    }
    relations = graph.build_database_relations(database_1, record_types=dbd.record_types)
    assert relations["record_a"]["record_b"] == [
        (
            database_1["record_a"].fields["INP"],
            RecordField(
                dtype="invalid",
                name="ABC",
                value="(invalid-record-type)",
                context=(LoadContext("unknown", 0),),
            ),
            ("CPP", "MS"),
        ),
    ]


def test_with_alias(dbd: Database):
    database_1 = {
        "record_a": create_record("ai", "record_a", {"INP": "foobar CPP MS", "VAL": "10"}),
        "record_b": create_record("ao", "record_b", {"VAL": "5"}),
    }
    relations = graph.build_database_relations(
        database_1, record_types=dbd.record_types,
        aliases={"foobar": "record_b"},
    )
    assert relations["record_a"]["record_b"] == [
        (
            database_1["record_a"].fields["INP"],
            database_1["record_b"].fields["VAL"],
            ("CPP", "MS"),
        ),
    ]


def test_combine_with_alias(dbd: Database):
    database_1 = {
        "record_a": create_record("ai", "record_a", {"INP": "record_b CPP MS", "VAL": "10"}),
        "record_b": create_record("ao", "record_b", {"OUT": "alias_c CA", "VAL": "20"}),
    }
    database_2 = {
        "record_c": create_record("ao", "record_c", {"OUT": "alias_d.INP", "VAL": "10"}),
        # Refer to record_a through
        "record_d": create_record("ai", "record_d", {"INP": "record_a", "VAL": "10"}),
        # ... but _also_ refer to it as alias_a; when combining the relations this makes
        # it more fun
        "record_e": create_record("ai", "record_e", {"INP": "alias_a CP", "VAL": "10"}),
    }
    relations = graph.build_database_relations(
        database_1,
        aliases={
            "alias_a": "record_a",
            "alias_b": "record_b",
        },
    )

    relations_2 = graph.build_database_relations(
        database_2,
        aliases={
            "alias_c": "record_c",
            "alias_d": "record_d",
            "alias_e": "record_e",
        },
    )

    graph.combine_relations(
        relations,
        database_1,
        relations_2,
        database_2,
        aliases={
            "alias_a": "record_a",
            "alias_b": "record_b",
            "alias_c": "record_c",
            "alias_d": "record_d",
            "alias_e": "record_e",
        },
    )

    assert relations["record_a"]["record_b"] == [
        (
            database_1["record_a"].fields["INP"],
            database_1["record_b"].fields["VAL"],
            ("CPP", "MS"),
        ),
    ]
    assert relations["record_b"]["record_a"] == [
        (
            database_1["record_b"].fields["VAL"],
            database_1["record_a"].fields["INP"],
            ("CPP", "MS"),
        ),
    ]
    assert relations["record_b"]["record_c"] == [
        (
            database_1["record_b"].fields["OUT"],
            # RecordField(
            #     dtype='unknown', name='VAL', value='(unknown-record)',
            #     context=(LoadContext("unknown", 0), ),
            # ),
            database_2["record_c"].fields["VAL"],
            ("CA", ),
        ),
    ]
    assert relations["record_c"]["record_d"] == [
        (
            database_2["record_c"].fields["OUT"],
            database_2["record_d"].fields["INP"],
            (),
        ),
    ]
    assert relations["record_d"]["record_c"] == [
        (
            database_2["record_d"].fields["INP"],
            database_2["record_c"].fields["OUT"],
            (),
        ),
    ]
    assert relations["record_d"]["record_a"] == [
        (
            database_2["record_d"].fields["INP"],
            database_1["record_a"].fields["VAL"],
            (),
        ),
    ]
    assert relations["record_e"]["record_a"] == [
        (
            database_2["record_e"].fields["INP"],
            database_1["record_a"].fields["VAL"],
            ("CP", ),
        ),
    ]
    assert relations["record_a"]["record_e"] == [
        (
            database_1["record_a"].fields["VAL"],
            database_2["record_e"].fields["INP"],
            ("CP", ),
        ),
    ]
