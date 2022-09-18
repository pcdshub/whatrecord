import dataclasses
import logging
import pathlib
from dataclasses import InitVar, field
from typing import Dict, List, Union

from .common import IocInfoDict, IocMetadata
from .util import run_script_with_json_output

logger = logging.getLogger(__name__)


class _IocInfoFinder:
    """
    An IOC information "finder" base class.

    Subclasses of this support different ways of finding IOCs from
    user-specified parameters.  See further information in subclasses.
    """
    def add_or_update_entry(self, info: IocMetadata):
        self.scripts[info.script] = info

    async def update(self):
        """
        Subclasses must implement this method.

        The backend server will call this periodically based on the
        user-configured settings.
        """
        ...


@dataclasses.dataclass
class IocScriptExternalLoader(_IocInfoFinder):
    """
    An IOC information "finder" that utilizes an external executable script.

    That script must return a JSON object that is compatible with
    `IocMetadata.from_dict`.
    """
    #: The script to run.
    load_script: str
    scripts: Dict[pathlib.Path, IocMetadata] = field(default_factory=dict)

    async def update(self):
        result = await run_script_with_json_output(self.load_script)
        for info in (result or {}):
            self.add_or_update_entry(IocMetadata.from_dict(info))
        return await super().update()


@dataclasses.dataclass
class IocScriptStaticInfoList(_IocInfoFinder):
    """
    An IOC information "finder" that is provided a list of IOC information
    dictionaries.

    This is mainly LCLS-specific as it integrates with their "IOC Manager"
    utility.
    """
    ioc_infos: InitVar[List[IocInfoDict]]
    scripts: Dict[pathlib.Path, IocMetadata] = field(default_factory=dict)

    def __post_init__(self, ioc_infos: List[IocInfoDict]):
        for info in ioc_infos:
            self.add_or_update_entry(IocMetadata.from_dict(info))


@dataclasses.dataclass
class IocScriptStaticList(_IocInfoFinder):
    """
    An IOC finder that does not do much finding; it expects a static list of
    scripts to load at startup.
    """
    script_list: InitVar[List[Union[str, pathlib.Path]]]
    scripts: Dict[pathlib.Path, IocMetadata] = field(default_factory=dict)

    def __post_init__(self, script_list: List[Union[str, pathlib.Path]]):
        for fn in script_list:
            self.add_or_update_entry(IocMetadata.from_file(fn))
