from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

from .. import util
from ..common import (IocMetadata, PVRelations, RecordField, RecordInstance,
                      RecordInstanceSummary, ScriptPVRelations, WhatRecord)


class TooManyRecordsError(Exception):
    ...


@dataclass
class ServerPluginSpec:
    name: str
    #: Python module
    module: Optional[str] = None
    #: Or any executable
    executable: Optional[List[str]] = None
    #: Can be a dataclass or a builtin type
    # result_class: type
    files_to_monitor: List[str] = field(default_factory=list)
    results: Any = None

    async def update(self):
        if self.executable:
            script = " ".join(f'"{param}"' for param in self.executable)
        elif self.module:
            script = f'"{sys.executable}" -m {self.module}'
        else:
            raise ValueError("module and executable both unset")

        results = await util.run_script_with_json_output(script)
        results = results or {}
        files_to_monitor = results.get("files_to_monitor", None)
        if files_to_monitor:
            self.files_to_monitor = files_to_monitor
        if "record_to_metadata" not in results:
            raise ValueError(f"Invalid plugin output: {results}")

        self.results = results
        return results


@dataclass
class PVGetInfo:
    pv_name: str
    present: bool
    info: List[WhatRecord]

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """\
{{ pv_name }}:
    In database: {{ present }}
{% for _info in info %}
{% set item_info = render_object(_info, "console") %}
    {{ item_info | indent(4)}}
{% endfor %}
}
""",
    }


@dataclass
class PVGetMatchesResponse:
    glob: str
    matches: List[str]


@dataclass
class IocGetMatchesResponse:
    glob: str
    matches: List[IocMetadata]


AnyRecordInstance = Union[RecordInstanceSummary, RecordInstance]


@dataclass
class IocGetMatchingRecordsResponse:
    ioc_glob: str
    pv_glob: str
    # TODO: ew, redo this
    matches: List[Tuple[IocMetadata, List[AnyRecordInstance]]]


@dataclass
class RecordFieldSummary:
    dtype: str
    name: str
    value: Any

    _jinja_format_: ClassVar[Dict[str, str]] = {
        "console": """field({{name}}, "{{value}}")""",
        "console-verbose": """\
field({{name}}, "{{value}}")
""",
    }


@dataclass
class PVLinkSummary:
    fields: Tuple[RecordFieldSummary, RecordFieldSummary]
    info: List[str]

    @classmethod
    def from_fields(
        cls,
        field1: RecordField,
        field2: RecordField,
        link_info: List[str]
    ) -> PVLinkSummary:
        return cls(
            fields=[
                RecordFieldSummary(dtype=field1.dtype, name=field1.name, value=field1.value),
                RecordFieldSummary(dtype=field2.dtype, name=field2.name, value=field2.value),
            ],
            info=link_info,
        )


PVRelationsSummary = Dict[
    str, Dict[str, List[PVLinkSummary]]
]


@dataclass
class PVRelationshipResponse:
    pv_relations: PVRelationsSummary
    script_relations: ScriptPVRelations
    ioc_to_pvs: Dict[str, List[str]]

    @classmethod
    def from_pv_relations(
        cls,
        pv_relations: PVRelations,
        script_relations: ScriptPVRelations,
        ioc_to_pvs: Dict[str, List[str]],
    ) -> PVRelationshipResponse:
        summary = {
            pv1: {
                pv2: [
                    PVLinkSummary.from_fields(
                        field1,
                        field2,
                        link_info
                    )
                    for field1, field2, link_info in links
                ]
                for pv2, links in pv2_items.items()
            }
            for pv1, pv2_items in pv_relations.items()
        }
        return cls(
            pv_relations=summary,
            script_relations=script_relations,
            ioc_to_pvs=ioc_to_pvs,
        )
