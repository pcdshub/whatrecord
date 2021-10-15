import pprint

import apischema
import pytest

from ..plugins import epicsarch
from . import conftest

ARCH_FILES = list((conftest.MODULE_PATH / "epicsarch").glob("*.txt"))

arch_filenames = pytest.mark.parametrize(
    "filename",
    [
        pytest.param(
            filename,
            id="/".join(filename.parts[-2:])
        )
        for filename in ARCH_FILES
    ]
)


@arch_filenames
def test_parse(filename):
    parsed = epicsarch.LclsEpicsArchFile.from_file(filename)

    serialized = apischema.serialize(parsed)
    pprint.pprint(serialized)
    apischema.deserialize(epicsarch.LclsEpicsArchFile, serialized)


def test_warnings():
    fn = conftest.MODULE_PATH / "epicsarch" / "test.txt"
    parsed = epicsarch.LclsEpicsArchFile.from_file(fn)

    from ..format import FormatContext

    ctx = FormatContext()
    print(ctx.render_object(parsed, "console"))

    types = [warning.type_ for warning in parsed.warnings]

    assert set(types) == {
        "duplicate_alias",
        "duplicate_pv",
        "alias_is_pv",
        "pv_is_alias",
        "missing_file",
        "recursive_include",
    }

    warning_texts = [warning.text for warning in parsed.warnings]
    assert any("Duplicate pvname: pvname5" in text for text in warning_texts)
    assert any("Alias name is a PV: pvname5" in text for text in warning_texts)
    assert any("PV name matches alias: descB" in text for text in warning_texts)
    assert any("missing" in text for text in warning_texts)
    assert any("Recursively included" in text for text in warning_texts)
