# cython: language_level=3

import contextlib
from typing import Dict, Union

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
    """
    A context for using EPICS macLib handle from Python.

    When other macro expansion tools just aren't enough, go with the one true
    macro expander - the one provided by EPICS - macLib.

    Parameters
    ----------
    show_warnings : bool, optional
        Show warnings (see ``macSuppressWarning``).

    string_encoding : str, optional
        The default string encoding to use.  Defaults to latin-1, as these
        tools were written before utf-8 was really a thing.
    """

    cdef MAC_HANDLE *handle
    _show_warnings: bool
    cdef public str string_encoding

    def __init__(self, show_warnings=False, string_encoding: str = "latin-1"):
        self.show_warnings = show_warnings
        self.string_encoding = string_encoding

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
        """A context manager to define macros (as kwargs) in a given scope."""
        macPushScope(self.handle)
        self.define(**macros)
        yield
        macPopScope(self.handle)

    def definitions_to_dict(self, defn: Union[str, bytes], string_encoding: str = "") -> Dict[str, str]:
        """Convert a definition string of the form ``A=value_a,B=value_a`` to a dictionary."""
        cdef char **pairs = NULL
        cdef int count

        string_encoding = string_encoding or self.string_encoding

        if not isinstance(defn, bytes):
            defn = defn.encode(string_encoding)

        count = macParseDefns(self.handle, defn, &pairs)
        if pairs == NULL or count <= 0:
            return {}

        result = {}
        for idx in range(count):
            variable = (pairs[2 * idx] or b'').decode(string_encoding)
            value = (pairs[2 * idx + 1] or b'').decode(string_encoding)
            result[variable] = value

        free(pairs)
        return result

    def define(self, **macros):
        """Use kwargs to define macros."""
        for key, value in macros.items():
            self.add_macro(
                str(key).encode(self.string_encoding),
                str(value).encode(self.string_encoding)
            )

    cdef int add_macro(self, key: bytes, value: bytes):
        cdef char** pairs = [key, value, NULL];
        return macInstallMacros(self.handle, pairs)

    def get_macro_details(self) -> Dict[str, str]:
        """
        Get a dictionary of full macro details.

        This represents the internal state of the MAC_ENTRY nodes.

        Included keys: name, rawval, value, type.
        """
        encoding = self.string_encoding
        result = {}
        cdef MAC_ENTRY* entry = <MAC_ENTRY*>self.handle.list.node.next
        while entry != NULL:
            if entry.name:
                result[entry.name] = {
                    "name": (entry.name or b"").decode(encoding),
                    "rawval": (entry.rawval or b"").decode(encoding),
                    "value": (entry.value or b"").decode(encoding),
                    "type": (entry.type or b"").decode(encoding),
                }
            entry = <MAC_ENTRY*>entry.node.next
        return result

    def get_macros(self) -> Dict[str, str]:
        """Get macros as a dictionary."""
        return dict(
            (macro["name"], macro["value"])
            for macro in self.get_macro_details().values()
        )

    def expand_with_length(self, value: str, max_length: int = 1024):
        """
        Expand a string, specifying the maximum length of the buffer.

        Trivia: 1024 is "MY_BUFFER_SIZE" in epics-base, believe it or not...
        """
        assert max_length > 0
        cdef char* buf = <char *>malloc(max_length)
        if not buf:
            raise MemoryError("Failed to allocate buffer")
        try:
            macExpandString(self.handle, value.encode(self.string_encoding), buf, max_length)
            # res = macExpandString...
            # if res < 0:
            #     raise ValueError(f"failed to expand: {res} ({value})")
            return buf.decode(self.string_encoding)
        finally:
            free(buf)

    def expand(self, value: str):
        """Expand a string, using the implicit buffer length of 1024 used in EPICS."""
        assert len(value) < 1024, "For large strings, use `expand_with_length`"
        cdef char buf[1024]
        macExpandString(self.handle, value.encode(self.string_encoding), buf, 1024)
        return buf.decode(self.string_encoding)
