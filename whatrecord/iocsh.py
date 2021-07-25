from typing import Optional

from _whatrecord.common import IocshRedirect, IocshSplit
from _whatrecord.iocsh import split_words

from .common import IocshResult, LoadContext
from .macro import MacroContext

__all__ = ["split_words", "parse_iocsh_line", "IocshRedirect", "IocshSplit"]


def parse_iocsh_line(
    line: str, *,
    context: Optional[LoadContext] = None,
    prompt: str = "epics>",
    macro_context: Optional[MacroContext] = None,
    string_encoding: str = "latin-1",
) -> IocshResult:
    """
    Parse an IOC shell line into an IocshResult.

    Parameters
    ----------
    line : str
       The line to parse.

    context : LoadContext, optional
       The load context to populate the result with.

    prompt : str, optional
       Replicating the EPICS source code, specify the state of the prompt
       here.  Defaults to "epics>".  If unset as in prior to IOC init,
       lines that do not start with "#-" will be eched.

    Returns
    -------
    IocshResult
       A partially filled IocshResult, ready for interpreting by a
       higher-level function.
    """
    result = IocshResult(
       context=context,
       line=line,
    )
    # Skip leading whitespace
    line = line.lstrip()

    if not line.startswith("#-"):
        result.outputs.append(line)

    if line.startswith('#'):
        # Echo non-empty lines read from a script.
        # Comments delineated with '#-' aren't echoed.
        return result

    if macro_context is not None:
        line = macro_context.expand(line)

    # * Skip leading white-space coming from a macro
    line = line.lstrip()

    # * Echo non-empty lines read from a script.
    # * Comments delineated with '#-' aren't echoed.
    if not prompt:
        if not line.startswith('#-'):
            result.outputs.append(line)

    # * Ignore lines that became a comment or empty after macro expansion
    if not line or line.startswith('#'):
        return result

    split = split_words(line, string_encoding=string_encoding)
    result.argv = split.argv

    # Only set the following if necessary; apischema can skip serialization
    # otherwise.
    if split.redirects:
        result.redirects = list(split.redirects.values())

    if split.error:
        result.error = split.error

    return result
