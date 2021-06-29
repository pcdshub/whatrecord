import dataclasses
import logging
import pathlib
from dataclasses import InitVar, field
from typing import Dict, List, Union

from .common import IocInfoDict, IocMetadata
from .util import run_script_with_json_output

logger = logging.getLogger(__name__)


class _IocInfoFinder:
    def add_or_update_entry(self, info: IocMetadata):
        self.scripts[info.script] = info

    async def update(self):
        ...


@dataclasses.dataclass
class IocScriptExternalLoader(_IocInfoFinder):
    load_script: str
    scripts: Dict[pathlib.Path, IocMetadata] = field(default_factory=dict)

    async def update(self):
        result = await run_script_with_json_output(self.load_script)
        for info in (result or {}):
            self.add_or_update_entry(IocMetadata.from_dict(info))
        return await super().update()


@dataclasses.dataclass
class IocScriptStaticInfoList(_IocInfoFinder):
    ioc_infos: InitVar[List[IocInfoDict]]
    scripts: Dict[pathlib.Path, IocMetadata] = field(default_factory=dict)

    def __post_init__(self, ioc_infos: List[IocInfoDict]):
        for info in ioc_infos:
            self.add_or_update_entry(IocMetadata.from_dict(info))


@dataclasses.dataclass
class IocScriptStaticList(_IocInfoFinder):
    script_list: InitVar[List[Union[str, pathlib.Path]]]
    scripts: Dict[pathlib.Path, IocMetadata] = field(default_factory=dict)

    def __post_init__(self, script_list: List[IocInfoDict]):
        for fn in script_list:
            self.add_or_update_entry(IocMetadata.from_filename(fn))
