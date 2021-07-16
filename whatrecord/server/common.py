from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

import apischema

from .. import util
from ..common import (IocMetadata, PVRelations, RecordInstance,
                      RecordInstanceSummary, ScriptPVRelations, WhatRecord)


class TooManyRecordsError(Exception):
    ...


@dataclass
class PluginResults:
    files_to_monitor: Dict[str, str]
    record_to_metadata_keys: Dict[str, List[str]]
    metadata_by_key: Dict[str, Any]
    metadata: Any
    execution_info: Dict[str, Any]
    # defines records? defines IOCs?


@dataclass
class ServerPluginSpec:
    name: str
    #: Python module
    module: Optional[str] = None
    #: Or any executable
    executable: Optional[List[str]] = None
    #: Can be a dataclass or a builtin type
    # result_class: type
    files_to_monitor: Dict[str, str] = field(default_factory=list)
    results: Optional[PluginResults] = None
    results_json: Any = None

    @property
    def script(self) -> str:
        """The script and arguments to run for the plugin."""
        if self.executable:
            return " ".join(f'"{param}"' for param in self.executable)
        elif self.module:
            return f'"{sys.executable}" -m {self.module}'
        raise ValueError("module and executable both unset")

    async def update(self) -> Optional[PluginResults]:
        """Call the plugin and get new information, storing it in results."""
        self.results_json = (
            await util.run_script_with_json_output(self.script)
        ) or {}
        self.files_to_monitor = self.results_json.get("files_to_monitor", {})
        self.results = apischema.deserialize(PluginResults, self.results_json)
        if self.results:
            self.files_to_monitor = self.results.files_to_monitor
        return self.results


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


PVRelationsSummary = Dict[str, List[str]]


@dataclass
class PVRelationshipResponse:
    pv_relations: PVRelations
    script_relations: ScriptPVRelations
    ioc_to_pvs: Dict[str, List[str]]


@dataclass
class PVShortRelationshipResponse:
    # pv_relations: PVRelationsSummary
    script_relations: ScriptPVRelations
    # ioc_to_pvs: Dict[str, List[str]]

    @classmethod
    def from_pv_relations(
        cls,
        pv_relations: PVRelations,
        script_relations: ScriptPVRelations,
        ioc_to_pvs: Dict[str, List[str]],
    ) -> PVRelationshipResponse:
        # summary = {
        #     pv1: list(pv2s)
        #     for pv1, pv2s in pv_relations.items()
        # }
        return cls(
            # pv_relations=summary,
            script_relations=script_relations,
            # ioc_to_pvs=ioc_to_pvs,
        )
