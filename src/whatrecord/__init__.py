import ctypes
import epicscorelibs.path

# Necessary unless [DY]LD_LIBRARY_PATH is set for epicscorelibs
ctypes.CDLL(epicscorelibs.path.get_lib("Com"))
ctypes.CDLL(epicscorelibs.path.get_lib("dbCore"))

del epicscorelibs.path
del ctypes

from .macro import MacroContext  # isort: skip  # noqa
from .iocsh import IOCShellInterpreter  # isort: skip  # noqa
from .db import DbdFile, load_database_file  # isort: skip  # noqa

__all__ = ["MacroContext", "IOCShellInterpreter", "DbdFile", "load_database_file"]
