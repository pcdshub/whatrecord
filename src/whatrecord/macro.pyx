# cython: language_level=3
import contextlib

cimport epicscorelibs
cimport epicscorelibs.Com
from libc.stdlib cimport free, malloc


cdef extern from "<ellLib.h>" nogil:
    cdef struct ELLNODE:
        ELLNODE *next
        ELLNODE *previous

    cdef struct ELLLIST:
        ELLNODE node   # Pointers to the first and last nodes on list
        int     count  # Number of nodes on the list


ctypedef struct MAC_ENTRY:
    # prev and next pointers
    ELLNODE     node
    # entry name
    char        *name
    # entry type
    char        *type
    # raw (unexpanded) value
    char        *rawval
    # expanded macro value
    char        *value
    # length of value
    size_t      length
    # error expanding value?
    int         error
    # ever been visited?
    int         visited
    # special (internal) entry?
    int         special
    # scoping level
    int         level


cdef extern from "<macLib.h>" nogil:
    ctypedef struct MAC_HANDLE:
        long        magic     # magic number (used for authentication)
        int         dirty     # values need expanding from raw values?
        int         level     # scoping level
        int         debug     # debugging level
        ELLLIST     list      # macro name / value list
        int         flags     # operating mode flags

    char *macEnvExpand(const char *str)
    MAC_HANDLE *macCreateHandle(MAC_HANDLE **handle, const char *pairs[])
    long macDeleteHandle(MAC_HANDLE *handle)
    long macExpandString(MAC_HANDLE *handle, const char *src, char *dest, long capacity)
    long macInstallMacros(MAC_HANDLE *handle, char *pairs[])
    long macParseDefns(MAC_HANDLE *handle, const char *defns, char **pairs[])
    void macPopScope(MAC_HANDLE *handle)
    void macPushScope(MAC_HANDLE *handle)
    void macSuppressWarning(MAC_HANDLE *handle, int)


cdef class MacroContext:
    cdef MAC_HANDLE *handle
    _show_warnings: bool

    def __init__(self, show_warnings=False):
        self.show_warnings = show_warnings

    @property
    def show_warnings(self):
        return self._show_warnings

    @show_warnings.setter
    def show_warnings(self, value: bool):
        self._show_warnings = bool(value)
        suppress = not self._show_warnings
        macSuppressWarning(self.handle, suppress)

    def __cinit__(self):
        if macCreateHandle(&self.handle, NULL):
            raise RuntimeError("Failed to initialize the handle")

    def __dealloc__(self):
        if self.handle is not NULL:
            macDeleteHandle(self.handle)
            self.handle = NULL

    @contextlib.contextmanager
    def scoped(self, **macros):
        macPushScope(self.handle)
        self.define(**macros)
        yield
        macPopScope(self.handle)

    def definitions_to_dict(self, defn: bytes):
        cdef char **pairs = NULL
        cdef int count
        count = macParseDefns(self.handle, defn, &pairs)
        if pairs == NULL or count <= 0:
            return {}

        result = {}
        for idx in range(count):
            variable = pairs[2 * idx]
            value = pairs[2 * idx + 1]
            result[variable or b''] = value or b''

        free(pairs)
        return result

    def define(self, **macros):
        for key, value in macros.items():
            self.add_macro(str(key).encode("utf-8"), str(value).encode("utf-8"))

    cdef int add_macro(self, key: bytes, value: bytes):
        cdef char** pairs = [key, value, NULL];
        return macInstallMacros(self.handle, pairs)

    def get_macro_details(self):
        result = {}
        cdef MAC_ENTRY* entry = <MAC_ENTRY*>self.handle.list.node.next
        while entry != NULL:
            if entry.name:
                result[entry.name] = {
                    "name": (entry.name or ""),
                    "rawval": (entry.rawval or ""),
                    "value": (entry.value or ""),
                    "type": (entry.type or ""),
                }
            entry = <MAC_ENTRY*>entry.node.next
        return result

    def get_macros(self):
        return dict(
            (macro["name"], macro["value"])
            for macro in self.get_macro_details().values()
        )

    def expand_with_length(self, value: str, max_length: int = 1024, encoding: str="utf-8"):
        # 1024 is "MY_BUFFER_SIZE" in epics-base, believe it or not...
        assert max_length > 0
        cdef char* buf = <char *>malloc(max_length)
        if not buf:
            raise MemoryError("Failed to allocate buffer")
        try:
            macExpandString(self.handle, value.encode(encoding), buf, max_length)
            # res = macExpandString...
            # if res < 0:
            #     raise ValueError(f"failed to expand: {res} ({value})")
            return buf.decode(encoding)
        finally:
            free(buf)

    def expand(self, value: str, encoding: str="utf-8"):
        # 1024 is "MY_BUFFER_SIZE" in epics-base, believe it or not...
        assert len(value) < 1024, "For large strings, use `expand_with_length`"
        cdef char buf[1024]
        macExpandString(self.handle, value.encode(encoding), buf, 1024)
        return buf.decode(encoding)
