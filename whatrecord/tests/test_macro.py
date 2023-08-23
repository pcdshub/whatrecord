import os

import apischema
import pytest

from .. import settings
from ..macro import MacroContext, PassthroughMacroContext


def test_skip_keys(monkeypatch):
    include_key = "_WR_TEST_INCLUDED"
    exclude_key = "_WR_TEST_TOKEN"
    monkeypatch.setattr(settings, "MACRO_INCLUDE_ENV", True)
    try:
        os.environ[exclude_key] = ""
        os.environ[include_key] = ""
        ctx = MacroContext(use_environment=True)
        keys = list(apischema.serialize(MacroContext, ctx)["macros"])
    finally:
        os.environ.pop(include_key, None)
        os.environ.pop(exclude_key, None)

    assert exclude_key not in keys
    assert include_key in keys


def test_skip_long_values(monkeypatch):
    include_key = "_WR_TEST_INCLUDED"
    exclude_key = "_WR_TEST_EXCLUDED"
    monkeypatch.setattr(settings, "MACRO_INCLUDE_ENV", True)
    try:
        os.environ[exclude_key] = "a" * (settings.MACRO_VALUE_MAX_LENGTH + 1)
        os.environ[include_key] = "a" * (settings.MACRO_VALUE_MAX_LENGTH - 2)
        ctx = MacroContext(use_environment=True)
        keys = list(apischema.serialize(MacroContext, ctx)["macros"])
    finally:
        os.environ.pop(include_key, None)
        os.environ.pop(exclude_key, None)

    assert exclude_key not in keys
    assert include_key in keys


@pytest.mark.parametrize("include", [False, True])
def test_env_include_exclude(monkeypatch, include: bool):
    monkeypatch.setattr(settings, "MACRO_INCLUDE_ENV", include)
    ctx = MacroContext(use_environment=True)
    keys = set(apischema.serialize(MacroContext, ctx)["macros"])
    assert not apischema.serialize(MacroContext, ctx)["passthrough"]

    if not include:
        assert set(keys) == set()
    else:
        assert 0 < len(set(keys)) <= len(os.environ)


def test_passthrough():
    ctx = PassthroughMacroContext()
    assert ctx.expand("$(ABC)") == "$(ABC)"

    serialized = apischema.serialize(MacroContext, ctx)
    assert serialized["passthrough"]

    deserialized = apischema.deserialize(MacroContext, serialized)
    assert isinstance(deserialized, PassthroughMacroContext)
    assert deserialized.expand("$(ABC)") == "$(ABC)"
