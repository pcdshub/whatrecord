import os

MAX_RECORD_LENGTH = int(os.environ.get("EPICS_MAX_RECORD_LENGTH", "60"))
EPICS_SITE_TOP = os.environ.get("EPICS_SITE_TOP", "/reg/g/pcds/epics")
MAX_RECORDS = int(os.environ.get("WHATRECORD_MAX_RECORDS", 200))
GDB_PATH = os.environ.get("WHATRECORD_GDB_PATH", "gdb")
CACHE_PATH = os.environ.get("WHATRECORD_CACHE_PATH", "")
DEFAULT_BASE_VERSION = os.environ.get("WHATRECORD_BASE_VERSION", "3.15")
WHATREC_SERVER = os.environ.get("WHATRECORD_SERVER", "http://localhost:8898/")
PLUGINS = os.environ.get("WHATRECORD_PLUGINS", "happi twincat_pytmc").split(" ")
SERVER_SCAN_PERIOD = int(os.environ.get("WHATRECORD_SERVER_SCAN_PERIOD", "600"))
TWINCAT_ROOT = os.environ.get("WHATRECORD_TWINCAT_ROOT", "")
AUTOSAVE_RELOAD_PERIOD = int(os.environ.get("WHATRECORD_AUTOSAVE_RELOAD_PERIOD", "60"))
