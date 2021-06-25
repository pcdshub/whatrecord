import asyncio
import os
import json
import logging

import pathlib
import apischema

from typing import Optional, Union, List

logger = logging.getLogger(__name__)


WHATRECORD_GDB_PATH = os.environ.get("WHATRECORD_GDB_PATH", "gdb")
MODULE_PATH = pathlib.Path(__file__).parent.resolve()


async def run_gdb(
    script: str,
    binary: Union[pathlib.Path, str],
    cls: type,
    args: Optional[List[str]] = None,
    gdb_path: str = WHATRECORD_GDB_PATH,
) -> dict:
    """Run a script and deserialize its output."""
    args = " ".join(f'"{arg}"' for arg in args or [])
    script_path = MODULE_PATH / f"{script}.py"
    to_execute = (
        f'"{gdb_path}" '
        f"--batch-silent "
        f'--command "{script_path}" '
        f'--args "{binary}" {args}'
    )

    proc = await asyncio.create_subprocess_shell(
        to_execute, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    (stdout, stderr) = await proc.communicate()
    if stderr:
        logger.warning(
            "Standard error output while running gdb (%r): %s", to_execute, stderr
        )

    if stdout:
        json_data = json.loads(stdout.decode("utf-8"))
    else:
        logger.warning("No standard output while getting GDB output (%r)", to_execute)
        json_data = {}

    try:
        return apischema.deserialize(cls, json_data)
    except Exception as ex:
        ex.json_data = json_data
        raise


def find_binary_from_hashbang(
    startup_script: Optional[Union[str, pathlib.Path]],
    must_exist: bool = False,
) -> Optional[str]:
    """
    Find the binary associated with a given startup script by looking at its
    shebang.

    Returns
    -------
    binary_path : str or None
        The path to the binary, if available.
    """
    if startup_script is None:
        return None

    try:
        with open(startup_script, "rt") as fp:
            first_line = fp.read().splitlines()[0]
    except Exception as ex:
        return None

    if first_line.startswith("#!"):
        parent_dir = pathlib.Path(startup_script).parent
        binary = parent_dir / first_line.lstrip("#!")
        if not must_exist or binary.exists():
            return str(binary.resolve())
