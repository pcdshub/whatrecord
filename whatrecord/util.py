import asyncio
import hashlib
import json
import logging
import pathlib
import textwrap
from typing import Dict, List, Optional, Tuple, TypeVar, Union

import apischema

from . import settings

logger = logging.getLogger(__name__)
MODULE_PATH = pathlib.Path(__file__).parent.resolve()


T = TypeVar("T")
AnyPath = Union[str, pathlib.Path]


def get_bytes_sha256(contents: bytes):
    """Hash a byte string with the SHA-256 algorithm."""
    return hashlib.sha256(contents).hexdigest()


def check_files_up_to_date(
    file_to_hash: Dict[AnyPath, str]
) -> bool:
    """
    Check if the provided files are up-to-date by way of recorded hash vs
    current hash.

    Parameters
    ----------
    file_to_hash : Dict[Union[str, pathlib.Path], str]
        File path to hash.

    Returns
    -------
    up_to_date : bool
        If all files maintain their stored hashes, returns True.
    """
    for fn, file_hash in file_to_hash.items():
        try:
            if get_file_sha256(fn) != file_hash:
                return False
        except FileNotFoundError:
            return False

    return True


def get_file_sha256(binary: AnyPath):
    """Hash a binary with the SHA-256 algorithm."""
    # This doesn't do any sort of buffering; but our binaries are pretty small
    # in comparison to what we're storing as metadata, anyway
    with open(binary, "rb") as fp:
        return hashlib.sha256(fp.read()).hexdigest()


def read_text_file_with_hash(
    fn: pathlib.Path,
    encoding="latin-1",
) -> Tuple[str, str]:
    """Hash a binary with the SHA-256 algorithm."""
    # This doesn't do any sort of buffering; but our binaries are pretty small
    # in comparison to what we're storing as metadata, anyway
    with open(fn, "rb") as fp:
        contents = fp.read()
    sha256 = hashlib.sha256(contents).hexdigest()
    return sha256, contents.decode(encoding)


async def run_script_with_json_output(
    script_line: str,
    encoding: str = "utf-8",
    log_errors: bool = True,
) -> Optional[dict]:
    """Run a script and get its JSON output."""
    proc = await asyncio.create_subprocess_shell(
        script_line,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    (stdout, stderr) = await proc.communicate()
    if stderr and log_errors:
        stderr_text = textwrap.indent(stderr.decode("utf-8", "replace"), "    ! ")
        logger.warning(
            "Standard error output while running script (%r):\n%s",
            script_line, stderr_text
        )

    if stdout:
        return json.loads(stdout.decode(encoding))

    if log_errors:
        logger.warning(
            "No standard output while running script (%r)",
            script_line
        )


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
    cache_path = pathlib.Path(settings.CACHE_PATH)
    binary_hash = get_file_sha256(binary)

    hash_filename = cache_path / f"{script}_{cls.__name__}_{binary_hash}.json"
    if use_cache:
        if not settings.CACHE_PATH or not cache_path.exists():
            use_cache = False
        else:
            try:
                with open(hash_filename, "rt") as fp:
                    json_data = json.load(fp)
                return apischema.deserialize(cls, json_data)
            except FileNotFoundError:
                ...
            except Exception as ex:
                logger.warning(
                    "Failed to load cached gdb information from disk; "
                    "re-running gdb (%s, filename=%s)",
                    ex,
                    hash_filename,
                    exc_info=True
                )

    args = " ".join(f'"{arg}"' for arg in args or [])
    script_path = MODULE_PATH / "plugins" / f"{script}.py"
    gdb_path = gdb_path or settings.GDB_PATH
    to_execute = (
        f'"{gdb_path}" '
        f"--batch-silent "
        f'--command "{script_path}" '
        f'--args "{binary}" {args}'
    )

    json_data = await run_script_with_json_output(to_execute)
    json_data = json_data or {}

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
        binary = parent_dir / first_line.lstrip("#!").strip()
        if not must_exist or binary.exists():
            return str(binary.resolve())
