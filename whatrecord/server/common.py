from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Generator, List, Optional, Tuple, Union

import apischema

from .. import util
from ..common import (IocMetadata, PVRelations, RecordInstance,
                      RecordInstanceSummary, ScriptPVRelations, WhatRecord)

logger = logging.getLogger(__name__)


class TooManyRecordsError(Exception):
    ...


@dataclass
class PluginResults:
    files_to_monitor: Dict[str, str] = field(default_factory=dict)
    record_to_metadata_keys: Dict[str, List[str]] = field(default_factory=dict)
    metadata_by_key: Dict[str, Any] = field(default_factory=dict)
    metadata: Any = None
    execution_info: Dict[str, Any] = field(default_factory=dict)
    nested: Optional[Dict[str, PluginResults]] = None

    def is_loaded_file(self, fn: str) -> bool:
        """Is the given file one that was loaded in the plugin?"""
        if fn in self.files_to_monitor:
            return True
        return any(
            nested.is_loaded_file(fn)
            for nested in (self.nested or {}).values()
        )

    def find_record_metadata(self, record: str) -> Generator[Any, None, None]:
        """Find all metadata for the given record name."""
        for key in self.record_to_metadata_keys.get(record) or []:
            try:
                yield self.metadata_by_key[key]
            except KeyError:
                logger.debug(
                    "Consistency error in plugin: missing metadata key(s) %r "
                    "for record %s",
                    key, record
                )

        for nested in (self.nested or {}).values():
            yield from nested.find_record_metadata(record)

    def find_by_key(self, key: str) -> Generator[Tuple[str, Any], None, None]:
        """Find all metadata for the given record name."""
        md = self.metadata_by_key.get(key, None)
        if md is not None:
            yield key, md

        for nest_key, nested in (self.nested or {}).items():
            for sub_key, info in nested.find_by_key(key):
                yield f"{nest_key}:{sub_key}", info


@dataclass
class ServerPluginSpec:
    name: str
    #: Python module
    module: Optional[str] = None
    #: Or any executable
    executable: Optional[List[str]] = None
    #: Can be a dataclass or a builtin type
    # result_class: type
    files_to_monitor: Dict[str, str] = field(default_factory=dict)
    results: Optional[PluginResults] = None
    results_json: Any = None
    # Require IOCs to be loaded first before running
    after_iocs: bool = False

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
    patterns: List[str]
    regex: bool
    matches: List[str]


@dataclass
class IocGetMatchesResponse:
    patterns: List[str]
    regex: bool
    matches: List[IocMetadata]


@dataclass
class IocGetDuplicatesResponse:
    patterns: List[str]
    regex: bool
    duplicates: Dict[str, List[str]]


AnyRecordInstance = Union[RecordInstanceSummary, RecordInstance]


@dataclass
class IocGetMatchingRecordsResponse:
    ioc_patterns: List[str]
    record_patterns: List[str]
    regex: bool
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
