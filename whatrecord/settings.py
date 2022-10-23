import os

_true_values = {"1", "y", "yes", "true"}

MAX_RECORD_LENGTH = int(os.environ.get("EPICS_MAX_RECORD_LENGTH", "60"))
EPICS_SITE_TOP = os.environ.get("EPICS_SITE_TOP", "/reg/g/pcds/epics")
MAX_RECORDS = int(os.environ.get("WHATRECORD_MAX_RECORDS", 200))
GDB_PATH = os.environ.get("WHATRECORD_GDB_PATH", "gdb")
CACHE_PATH = os.environ.get("WHATRECORD_CACHE_PATH", "")
DEFAULT_BASE_VERSION = os.environ.get("WHATRECORD_BASE_VERSION", "3.15")
WHATREC_SERVER = os.environ.get("WHATRECORD_SERVER", "http://localhost:8898/")
PLUGINS = os.environ.get("WHATRECORD_PLUGINS", "happi twincat_pytmc netconfig epicsarch").split(" ")
SERVER_SCAN_PERIOD = int(os.environ.get("WHATRECORD_SERVER_SCAN_PERIOD", "600"))
AUTOSAVE_RELOAD_PERIOD = int(os.environ.get("WHATRECORD_AUTOSAVE_RELOAD_PERIOD", "60"))

# WHATRECORD_OUTPUT_INDENT (int) - indentation in spaces when rendering output.
INDENT = int(os.environ.get("WHATRECORD_OUTPUT_INDENT", "4"))

# WHATRECORD_MACRO_KEY_SKIP (str) - keys to skip, specified by regular
# expressions.  Should be valid Python syntax for a list of strings, as it
# will be handed to ``ast.literal_eval``.
MACRO_KEY_SKIP = os.environ.get("WHATRECORD_MACRO_KEY_SKIP", "")
# WHATRECORD_MACRO_NO_ENV (bool) - do not serialize *any* environment
# variables if set to 1.
MACRO_NO_ENV = os.environ.get("WHATRECORD_MACRO_NO_ENV", "true").lower() in _true_values
# WHATRECORD_MACRO_VALUE_MAX_LENGTH (int) - maximum length of macro values to
# serialize. 0 to disable maximum length check.
MACRO_VALUE_MAX_LENGTH = int(os.environ.get("WHATRECORD_MACRO_VALUE_MAX_LENGTH", 1024))
