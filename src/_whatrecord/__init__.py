def _preload_shared_libraries():
    """
    Pre-load epicscorelibs shared libraries.

    Ensuring we find the ones distributed with whatrecord.
    """
    import ctypes
    import pathlib
    import sys

    module_path = pathlib.Path(__file__).resolve().parent

    extension = {
        "darwin": "dylib",
        "linux": "so",
        "windows": "dll"
    }.get(sys.platform, "so")

    for lib_prefix in ["libCom", "libca", "libdbCore"]:
        for lib in module_path.glob(f"{lib_prefix}*.{extension}"):
            ctypes.CDLL(str(lib))


_preload_shared_libraries()

from . import iocsh, macro  # noqa  # isort: skip

__all__ = ["iocsh", "macro"]
