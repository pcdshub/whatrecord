import ctypes

import epicscorelibs.path

# Necessary unless [DY]LD_LIBRARY_PATH is set for epicscorelibs
ctypes.CDLL(epicscorelibs.path.get_lib("Com"))
ctypes.CDLL(epicscorelibs.path.get_lib("dbCore"))

del epicscorelibs.path
del ctypes

# from . import iocsh, macro

# __all__ = ["iocsh", "macro"]
