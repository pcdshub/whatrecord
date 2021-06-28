import asyncio
import hashlib
import json
import logging
import pathlib
from typing import List, Optional, TypeVar, Union

import apischema

from . import settings

logger = logging.getLogger(__name__)
MODULE_PATH = pathlib.Path(__file__).parent.resolve()


T = TypeVar("T")


def get_file_sha256(binary: pathlib.Path):
    """Hash a binary with the SHA-256 algorithm."""
    # This doesn't do any sort of buffering; but our binaries are pretty small
    # in comparison to what we're storing as metadata, anyway
    with open(binary, "rb") as fp:
        return hashlib.sha256(fp.read()).hexdigest()


async def run_gdb(
    script: str,
    binary: Union[pathlib.Path, str],
    cls: T,
    args: Optional[List[str]] = None,
    gdb_path: Optional[str] = None,
    use_cache: bool = True,
) -> T:
    """
    Run a script and deserialize its output.

    Parameters
    ----------
    script : str
        The script name to run (whatrecord.__script__, omitting .py)

    binary : str or pathlib.Path
        The binary file to load into GDB.

    cls : type
        The dataclass type to deserialize gdb's output to.

    args : list, optional
        List of string arguments to pass to gdb.

    gdb_path : str, optional
        The path to the gdb binary.  Defaults to ``WHATRECORD_GDB_PATH``
        from the environment (``gdb``).
    """
    cache_path = pathlib.Path(settings.GDB_CACHE)
    binary_hash = get_file_sha256(binary)

    hash_filename = cache_path / f"{script}_{cls.__name__}_{binary_hash}.json"
    if use_cache:
        if not settings.GDB_CACHE or not cache_path.exists():
            use_cache = False
        elif hash_filename.exists():
            with open(hash_filename, "rt") as fp:
                json_data = json.load(fp)
            return apischema.deserialize(cls, json_data)

    args = " ".join(f'"{arg}"' for arg in args or [])
    script_path = MODULE_PATH / f"{script}.py"
    gdb_path = gdb_path or settings.GDB_PATH
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

    if use_cache:
        with open(hash_filename, "wt") as fp:
            json.dump(json_data, fp, indent=4)

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
    except Exception:
        return None

    if first_line.startswith("#!"):
        parent_dir = pathlib.Path(startup_script).parent
        binary = parent_dir / first_line.lstrip("#!")
        if not must_exist or binary.exists():
            return str(binary.resolve())
