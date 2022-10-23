import os

import apischema
import pytest

from .. import settings
from ..macro import MacroContext


def test_skip_keys():
    include_key = "_WR_TEST_INCLUDED"
    exclude_key = "_WR_TEST_TOKEN"
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


def test_skip_long_values():
    include_key = "_WR_TEST_INCLUDED"
    exclude_key = "_WR_TEST_EXCLUDED"
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


@pytest.mark.parametrize("exclude", [False, True])
def test_env_include_exclude(monkeypatch, exclude: bool):
    monkeypatch.setattr(settings, "MACRO_NO_ENV", exclude)
    ctx = MacroContext(use_environment=True)
    keys = set(apischema.serialize(MacroContext, ctx)["macros"])

    if exclude:
        assert set(keys) == set()
    else:
        assert 0 < len(set(keys)) <= len(os.environ)
