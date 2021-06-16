"""Placeholder for PVA parsing tests, for the most part..."""

from whatrecord import Database
from whatrecord.db import LoadContext, PVAFieldReference, RecordInstance


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
                metadata={},
            ),
            "Y": PVAFieldReference(
                context=(LoadContext("None", 12), ),
                name="Y",
                record_name="rec:Y",
                field_name="VAL",
                metadata={},
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
