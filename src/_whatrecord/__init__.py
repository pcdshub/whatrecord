def _preload_shared_libraries():
    """
    Pre-load epicscorelibs shared libraries.

    Ensuring we find the ones distributed with whatrecord.
    """
    import ctypes
    import pathlib
    import sys

    module_path = pathlib.Path(__file__).resolve().parent

    pattern = {
        "darwin": "{lib_prefix}*.dylib",
        "linux": "{lib_prefix}.so.*",
        "windows": "{lib_prefix}*.dll"
    }.get(sys.platform, "{lib_prefix}.so.*")

    for lib_prefix in ["libCom", "libca", "libdbCore"]:
        for lib in module_path.glob(pattern.format(lib_prefix=lib_prefix)):
            ctypes.CDLL(str(lib))


_preload_shared_libraries()

from . import iocsh, macro  # noqa  # isort: skip

__all__ = ["iocsh", "macro"]
