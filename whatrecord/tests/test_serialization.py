import dataclasses
import importlib
import inspect
import logging
import pkgutil
import re
import sys
import typing
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional, Union

import apischema
import pytest

from .. import (access_security, asyn, autosave, cache, common, ioc_finder,
                motor, shell)
from ..common import FullLoadContext, LoadContext

MODULE_PATH = Path(__file__).parent

logger = logging.getLogger(__name__)

SKIP_CLASSES = (
    cache.Cached,
    ioc_finder.IocScriptStaticInfoList,
    ioc_finder.IocScriptStaticList,
)

SKIP_DESERIALIZATION = {
    # These take too long to round-trip and verify somehow:
    shell.LoadedIoc,
    shell.ShellState,
    autosave.AutosaveState,
    asyn.AsynState,
    motor.MotorState,
    access_security.AccessSecurityState,
}


def find_whatrecord_submodules() -> Dict[str, ModuleType]:
    """Find all whatrecord submodules, as a dictionary of name to module."""
    modules = {}
    package_root = str(MODULE_PATH.parent)
    for item in pkgutil.walk_packages(path=[package_root], prefix="whatrecord."):
        if item.name.endswith("__main__"):
            continue
        try:
            modules[item.name] = sys.modules[item.name]
        except KeyError:
            # Submodules may not yet be imported; do that here.
            try:
                modules[item.name] = importlib.import_module(
                    item.name, package="whatrecord"
                )
            except Exception:
                logger.exception("Failed to import %s", item.name)

    return modules


def find_all_dataclasses() -> List[type]:
    """Find all dataclasses in whatrecord and return them as a list."""

    def should_include(obj):
        return (
            inspect.isclass(obj)
            and dataclasses.is_dataclass(obj)
            and obj not in SKIP_CLASSES
        )

    def sort_key(cls):
        return (cls.__module__, cls.__name__)

    devices = [
        obj
        for module in find_whatrecord_submodules().values()
        for _, obj in inspect.getmembers(module, predicate=should_include)
    ]

    return list(sorted(set(devices), key=sort_key))


dataclass_name_to_class = {cls.__name__: cls for cls in find_all_dataclasses()}

all_dataclasses = pytest.mark.parametrize(
    "cls", [pytest.param(cls, id=name) for name, cls in dataclass_name_to_class.items()]
)


init_args_by_type = {
    Optional[List[LoadContext]]: None,
    Optional[common.IocMetadata]: None,
    Optional[str]: None,
    Path: Path(),
    Union[int, str]: "abc",
    Union[shell.IocLoadFailure, str]: "use_cache",
    Union[str, List[str]]: ["a", "b", "c"],
    bool: True,
    bytes: b"testing",
    FullLoadContext: [LoadContext("test", 1)],
    LoadContext: LoadContext("test", 1),
    dict: {},
    float: 10,
    int: 10,
    list: [],
    re.Pattern: re.compile("abc"),
    str: "testing",
    typing.Any: 123,
    typing.Tuple[str, str]: ("a", "b"),
    Optional[common.RecordDefinitionAndInstance]: None,
    Optional[common.RecordInstance]: None,
    Optional[common.RecordType]: None,
}


def try_to_instantiate(cls):
    kwargs = {}
    fields = dataclasses.fields(cls)
    type_hints = apischema.utils.get_type_hints(cls)
    for field in fields:
        if (
            field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        ):
            continue

        field_type = type_hints[field.name]
        if field_type in init_args_by_type:
            kwargs[field.name] = init_args_by_type[field_type]
        elif str(field_type) in init_args_by_type:
            kwargs[field.name] = init_args_by_type[str(field_type)]
        elif dataclasses.is_dataclass(field_type):
            kwargs[field.name] = try_to_instantiate(field_type)
        else:
            origin = apischema.typing.get_origin(field_type)
            try:
                kwargs[field.name] = init_args_by_type[origin]
            except KeyError:
                raise ValueError(f"Missing in dict: {field_type} ({origin})")

    return cls(**kwargs)


@all_dataclasses
def test_serialize(cls):
    instance = try_to_instantiate(cls)
    serialized = apischema.serialize(instance)
    print(cls)
    print("Serialized:")
    print(serialized)
    deserialized = apischema.deserialize(cls, serialized)
    print("Deserialized:")
    print(deserialized)
    if cls not in SKIP_DESERIALIZATION:
        assert deserialized == instance
