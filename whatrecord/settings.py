import os

_true_values = {"1", "y", "yes", "true"}

# Maximum number of records to return in a single query for the frontend:
MAX_RECORDS = int(os.environ.get("WHATRECORD_MAX_RECORDS", 200))
# Path to the gdb binary to use for symbol introspection:
GDB_PATH = os.environ.get("WHATRECORD_GDB_PATH", "gdb")
# A path to cache parsed and serialized IOC information and other (e.g., gdb
# binary information):
CACHE_PATH = os.environ.get("WHATRECORD_CACHE_PATH", "")
# The default epics-base version to assume, where not specified otherwise.
DEFAULT_BASE_VERSION = os.environ.get("WHATRECORD_BASE_VERSION", "3.15")
# The server host to use (for the client)
WHATREC_SERVER = os.environ.get("WHATRECORD_SERVER", "http://localhost:8898/")
# List of plugins to enable.
PLUGINS = os.environ.get("WHATRECORD_PLUGINS", "happi twincat_pytmc netconfig epicsarch").split(" ")
# Period, in seconds, to scan for updated IOCs or files
SERVER_SCAN_PERIOD = int(os.environ.get("WHATRECORD_SERVER_SCAN_PERIOD", "600"))
# Period, in seconds, to reload autosave .sav files
AUTOSAVE_RELOAD_PERIOD = int(os.environ.get("WHATRECORD_AUTOSAVE_RELOAD_PERIOD", "60"))

# WHATRECORD_OUTPUT_INDENT (int) - indentation in spaces when rendering output.
INDENT = int(os.environ.get("WHATRECORD_OUTPUT_INDENT", "4"))

# WHATRECORD_MACRO_KEY_SKIP (str) - keys to skip, specified by regular
# expressions.  Should be valid Python syntax for a list of strings, as it
# will be handed to ``ast.literal_eval``.
MACRO_KEY_SKIP = os.environ.get("WHATRECORD_MACRO_KEY_SKIP", "")
# WHATRECORD_MACRO_INCLUDE_ENV (bool) - serialize environment variables if set
# to 1.
MACRO_INCLUDE_ENV = os.environ.get("WHATRECORD_MACRO_INCLUDE_ENV", "true").lower() in _true_values
# WHATRECORD_MACRO_VALUE_MAX_LENGTH (int) - maximum length of macro values to
# serialize. 0 to disable maximum length check.
MACRO_VALUE_MAX_LENGTH = int(os.environ.get("WHATRECORD_MACRO_VALUE_MAX_LENGTH", 1024))

# A SLAC-specific setting (other facilities may ignore this):
EPICS_SITE_TOP = os.environ.get("EPICS_SITE_TOP", "/reg/g/pcds/epics")
