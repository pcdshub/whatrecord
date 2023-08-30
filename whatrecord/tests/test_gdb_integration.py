import shutil
import sys

import pytest

from ..common import IocMetadata

SUPPORTED_PLATFORM = sys.platform in {"linux"}


platform_skip = pytest.mark.skipif(
    not SUPPORTED_PLATFORM,
    reason=f"Not supported on {sys.platform}",
)

gdb_unavailable_skip = pytest.mark.skipif(
    shutil.which("gdb") is None,
    reason="GDB unavailable"
)


softioc = shutil.which("softIoc")

softioc_unavailable_skip = pytest.mark.skipif(
    softioc is None,
    reason="softIoc unavailable"
)


@pytest.mark.xfail(reason="Makes too many SLAC/LCLS/PCDS/ECS assumptions.")
@pytest.mark.asyncio
@platform_skip
@gdb_unavailable_skip
@softioc_unavailable_skip
async def test_gdb_info():
    md = IocMetadata(binary=str(softioc))

    info = await md.get_binary_information()
    assert info is not None, "Script appears to have failed"
    print("Got information", info)

    assert len(md.variables)
    assert len(md.commands)
    assert md.variables == info.variables
    assert md.commands == info.commands
    assert md.base_version == info.base_version
    assert any(
        (
            "3." in md.base_version,
            "7." in md.base_version,
        )
    )
    assert "dbLoadRecords" in md.commands
    assert "CASDEBUG" in md.variables
