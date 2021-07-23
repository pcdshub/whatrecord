# cython: language_level=3

from .common import IocshRedirect, IocshSplit


def _get_redirect(redirects: dict, idx: int) -> IocshRedirect:
    if idx not in redirects:
        redirects[idx] = IocshRedirect(fileno=idx, name="", mode="")
    return redirects[idx]


cpdef split_words(
    input_line: str,
    string_encoding: str = 'latin-1',
    ifs: bytes = b" \t(),\r",
    num_redirects: int = 5,
):
    """
    Split ``input_line`` into words, according to how the IOC shell would.

    Note that this is almost a direct conversion of the original C code, making
    an attempt to avoid introducing inconsistencies between this implementation
    and the original.

    Parameters
    ----------
    input_line : str
        The line to split.

    Returns
    -------
    info : IocshSplit
    """
    cdef int EOF = -1
    cdef int inword = 0
    cdef int quote = EOF
    cdef int backslash = 0
    cdef int idx = 0
    cdef int idx_out = 0
    cdef int length
    cdef int redirectFd = 1
    cdef dict redirects = {}
    cdef char c
    cdef object redirect = None
    cdef list word_starts = []

    cdef bytearray input_line_bytes = bytearray(input_line.encode(string_encoding))
    input_line_bytes.append(0)

    # Implicit access to underlying buffer of ``input_line_bytes``;
    # modify line, modify input_line_bytes.  No additional allocation
    # or free required here.
    cdef char *line = input_line_bytes

    while idx < len(input_line_bytes) - 1:
        c = line[idx]
        sep = (quote == EOF and not backslash and c in ifs)
        idx += 1

        if quote == EOF and not backslash:
            if c == b'\\':
                backslash = 1
                continue
            if c == b'<':
                if redirect:
                    break

                redirect = _get_redirect(redirects, 0)
                sep = 1
                redirect.mode = "r"

            if b'1' <= c <= b'9' and line[idx] == b'>':
                redirectFd = c - ord(b'0')
                c = b'>'
                idx += 1

            if c == b'>':
                if redirect:
                    break
                if redirectFd >= num_redirects:
                    redirect = _get_redirect(redirects, 1)
                    break
                redirect = _get_redirect(redirects, redirectFd)
                sep = 1
                if line[idx] == b'>':
                    idx += 1
                    redirect.mode = "a"
                else:
                    redirect.mode = "w"

        if inword:
            if c == quote:
                quote = EOF
            elif quote == EOF and not backslash:
                if sep:
                    inword = 0
                    line[idx_out] = 0
                    idx_out += 1
                elif c == b'"' or c == b"'":
                    quote = c
                else:
                    line[idx_out] = c
                    idx_out += 1
            else:
                line[idx_out] = c
                idx_out += 1
        elif not sep:
            if (c == b'"' or c == b'\'') and not backslash:
                quote = c
            if redirect:
                if redirect.name:
                    break
                redirect.name = idx_out
                redirect = None
            else:
                word_starts.append(idx_out)
            if quote == EOF:
                line[idx_out] = c
                idx_out += 1
            inword = 1
        backslash = 0

    if inword and idx_out < len(input_line_bytes):
        line[idx_out] = 0
        idx_out += 1

    # Python-only as we're not dealing with pointers to the string;
    # fix up redirect names by looking back at ``line``
    for _redir in redirects.values():
        if isinstance(_redir.name, int):
            offset = _redir.name
            _redir.name = str(&line[offset], string_encoding)
        elif not _redir.name:
            error = f"Illegal redirection. ({_redir})"

    error = None
    if redirect is not None:
        error = f"Illegal redirection. ({redirect})"
    elif word_starts:
        if quote != EOF:
            error = f"Unbalanced quote. ({quote})"
        elif backslash:
            error = "Trailing backslash."

    return IocshSplit(
        argv=[
            str(&line[word_start], string_encoding)
            for word_start in word_starts
        ],
        redirects=redirects,
        error=error,
    )
