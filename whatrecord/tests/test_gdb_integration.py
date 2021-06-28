import asyncio
import shutil
import sys
from typing import Optional

import pytest

from ..common import GdbBinaryInfo, IocMetadata

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


@platform_skip
@gdb_unavailable_skip
@softioc_unavailable_skip
def test_gdb_info():
    md = IocMetadata(binary=str(softioc))

    async def inner() -> Optional[GdbBinaryInfo]:
        return await md.get_binary_information()

    loop = asyncio.get_event_loop()
    info = loop.run_until_complete(inner())

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
