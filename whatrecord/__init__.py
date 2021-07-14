from ._version import get_versions

__version__ = get_versions()['version']
del get_versions

from .macro import MacroContext  # isort: skip  # noqa
from .iocsh import parse_iocsh_line  # isort: skip  # noqa
from .db import Database, load_database_file  # isort: skip  # noqa

__all__ = ["MacroContext", "parse_iocsh_line", "Database", "load_database_file"]
