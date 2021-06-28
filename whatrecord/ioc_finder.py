import asyncio
import dataclasses
import json
import logging
import pathlib
from dataclasses import InitVar, field
from typing import Dict, List, Union

from whatrecord.common import IocInfoDict, IocMetadata

logger = logging.getLogger(__name__)


async def load_from_external_script(script_line: str) -> List[IocInfoDict]:
    """Run a script and get its JSON output."""
    proc = await asyncio.create_subprocess_shell(
        script_line,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    (stdout, stderr) = await proc.communicate()
    if stderr:
        logger.warning(
            "Standard error output while updating IOCs (%r): %s",
            script_line, stderr
        )

    if stdout:
        return json.loads(stdout.decode("utf-8"))

    logger.warning(
        "No standard output while updating IOCs (%r)",
        script_line
    )
    return []


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
        for info in await load_from_external_script(self.load_script):
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
