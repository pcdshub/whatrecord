"""PVA/V4-related parsing tests"""

import math
import textwrap
from typing import Optional

import lark
import pytest

from ..common import LoadContext
from ..db import Database, PVAFieldReference, RecordField, RecordInstance
from ..format import FormatContext, FormatOptions


def test_simple():
    db = Database.from_string(
        """
record(ai, "rec:X") {
  info(Q:group, {
    "grp:name": {
        "X": {+channel:"VAL"}
    }
  })
}
record(ai, "rec:Y") {
  info(Q:group, {
    "grp:name": {
        "Y": {+channel:"VAL"}
    }
  })
}
""")
    assert db.pva_groups["grp:name"] == RecordInstance(
        context=(LoadContext("None", 4), ),
        record_type="PVA",
        name="grp:name",
        is_pva=True,
        fields={
            "X": PVAFieldReference(
                context=(LoadContext("None", 5), ),
                name="X",
                record_name="rec:X",
                field_name="VAL",
                metadata={"+channel": "VAL"},
            ),
            "Y": PVAFieldReference(
                context=(LoadContext("None", 12), ),
                name="Y",
                record_name="rec:Y",
                field_name="VAL",
                metadata={"+channel": "VAL"},
            ),
        }
    )


def test_link_equivalence():
    # record(longin, "src") {
    #     field(INP, {pva:{
    #         pv:"tgt",
    #         field:"",
    #         local:false,
    #         Q:4,
    #         pipeline:false,
    #         proc:none,
    #         sevr:false,
    #         time:false,
    #         monorder:0,
    #         retry:false,
    #         always:false,
    #         defer:false
    #     }})
    # }
    Database.from_string(
        """
record(longin, "tgt1") {}
record(longin, "src1") {
    field(INP, {pva:"tgt1"})
}

record(longin, "tgt2") {}
record(longin, "src2") {
    field(INP, {pva:{pv:"tgt2"}})
}
"""
    )

    # TODO check src1 vs src2


def test_other_stuff():
    Database.from_string(
        """
record(ai, "time_tag") {
  info(Q:time:tag, "nsec:lsb:20")
}

record(ai, "display_form_hint") {
  info(Q:form, "Default") # implied default
}

record(longin, "tgt3") {}
record(longin, "src3") {
    field(INP, {pva:{
        pv:"tgt3",
        field:"",   # may be a sub-field
        local:false,# Require local PV
        Q:4,        # monitor queue depth
        pipeline:false, # require that server uses monitor flow control protocol
        proc:none,  # Request record processing (side-effects).
        sevr:false, # Maximize severity.
        time:false, # set record time during getValue
        monorder:0, # Order of record processing as a result of CP and CPP
        retry:false,# allow Put while disconnected.
        always:false,# CP/CPP input link process even when .value field hasn't changed
        defer:false # Defer put
    }})
}
"""
    )


@pytest.mark.xfail
def test_numbers():
    db = Database.from_string(
        """
record(ai, "value") {
    field(NAN, NaN)
    field(HEXINT, 0x10)
    field(VAL, {"a": 1e10})
}
""")

    # I think json_string is taking priority, meaning we faithfully get
    # back the strings, but we don't interpret the "number" rule at all.
    # All numbers then become strings, which isn't exactly ideal, but
    # also not a deal-breaker for the most part.
    assert db.records["value"].fields["NAN"].value is math.nan
    assert db.records["value"].fields["HEXINT"].value == 0x10
    assert db.records["value"].fields["VAL"].value == {"a": 1e10}


def test_tab_in_field():
    # Believe it or not, tabs are not accepted in fields in V4 (V3 is more lax)
    with pytest.raises(lark.UnexpectedToken):
        Database.from_string(
            """\
record(ai, "rec:X") {
    field(A, "test\tvalue")
}
"""
        )


def test_list_as_value():
    db = Database.from_string(
        """\
record(ai, "rec:X") {
    field(VAL, ["test value"])
}
""",
        version=4,
    )
    val = db.records["rec:X"].fields["VAL"]
    assert isinstance(val, RecordField)
    assert val.value == ("test value",)


@pytest.mark.parametrize(
    "input_text, expected",
    [
        pytest.param(
            """\
            menu(stringoutPOST) {
                choice(stringoutPOST_OnChange, "On Change")
                choice(stringoutPOST_Always, "Always")
            }
            recordtype(ai) {
                %#include "epicsTypes.h"
                %#include "link.h"
                field(NAME, DBF_STRING) {
                    prompt("Record Name")
                    special(SPC_NOMOD)
                    size(61)
                }
            }
            device(ai, CONSTANT, devAaiSoft, "Soft Channel")
            link(state, lnkStateIf)
            registrar(rsrvRegistrar)
            variable(dbBptNotMonotonic, int)
            """,
            None,
            id="dbd_basic"
        ),
        pytest.param(
            """\
            record(ai, "rec:X") {
                field(A, "test")
                field(B, "test")
                info(info, "X")
            }
            """,
            None,
            id="record_basic"
        ),
        pytest.param(
            """\
            record(ai, "rec:X") {
                info(Q:group, {
                    "grp:name": {
                        "X": {
                            "+channel": "VAL"
                        }
                    }
                })
            }

            record(ai, "rec:Y") {
                info(Q:group, {
                    "grp:name": {
                        "Y": {
                            "+channel": "VAL"
                        }
                    }
                })
            }
            """,
            None,
            id="pva_group_1",
        ),
    ],
)
def test_roundtrip_format(input_text: str, expected: Optional[str]):
    input_text = textwrap.dedent(input_text)
    ctx = FormatContext(options=FormatOptions(indent=4))

    db = Database.from_string(input_text, version=4)
    result = ctx.render_object(db, "file")
    if expected is None:
        assert result.strip() == input_text.strip()
    else:
        expected = textwrap.dedent(expected)
        assert result.strip() == expected.strip()
