import os

MAX_RECORD_LENGTH = int(os.environ.get("EPICS_MAX_RECORD_LENGTH", "60"))
EPICS_SITE_TOP = os.environ.get("EPICS_SITE_TOP", "/reg/g/pcds/epics")
MAX_RECORDS = int(os.environ.get("WHATRECORD_MAX_RECORDS", 200))
GDB_PATH = os.environ.get("WHATRECORD_GDB_PATH", "gdb")
DEFAULT_BASE_VERSION = os.environ.get("WHATRECORD_BASE_VERSION", "3.15")
WHATREC_SERVER = os.environ.get("WHATREC_SERVER", "http://localhost:8898/")
