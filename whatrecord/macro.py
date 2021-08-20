from typing import Dict

from _whatrecord.macro import MacroContext


def macros_from_string(
    macro_string: str, use_environment: bool = False
) -> Dict[str, str]:
    """
    Get a macro dictionary from a macro string.

    Parameters
    ----------
    macro_string : str
        The macro string, in the format A=B,C=D,...

    use_environment : bool, optional
        Use environment variables as well.  Defaults to False.

    Returns
    -------
    macros : Dict[str, str]
        Macro key to value.
    """
    if not macro_string.strip():
        return {}
    macro_context = MacroContext(use_environment=use_environment)
    return macro_context.define_from_string(macro_string)


__all__ = ["MacroContext", "macros_from_string"]
