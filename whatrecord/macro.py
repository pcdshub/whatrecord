import ast
import dataclasses
import os
import re
from typing import Any, Dict, Optional

import apischema
from epicsmacrolib import MacroContext

from . import settings


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


@dataclasses.dataclass
class _SerializedMacroContext:
    #: Show warnings
    show_warnings: bool
    #: String encoding to use internally with macLib.
    string_encoding: str
    #: The macros, including any environment variables (if use_environment set).
    macros: Dict[str, str]


RE_MACRO_KEY_SKIP = []

# This becomes more of a concern when run on CI.
# Consider tweaking this for your purposes in MACRO_KEY_SKIP or
# setting MACRO_NO_ENV for CI jobs.
MACRO_KEY_SKIP_DEFAULT = [
    ".*TOKEN.*",
    ".*SECRET.*",
    ".*SSH.*",
    ".*GITHUB.*",
]


def set_serialization_settings(skip: Optional[str] = settings.MACRO_KEY_SKIP):
    """Update macro serialization settings."""
    global RE_MACRO_KEY_SKIP
    if skip:
        skip_regex = ast.literal_eval(skip)
    else:
        skip_regex = MACRO_KEY_SKIP_DEFAULT
    RE_MACRO_KEY_SKIP = [re.compile(regex) for regex in skip_regex]


set_serialization_settings()


def should_serialize_key(key: str, value: str) -> bool:
    """
    Should ``key`` be serialized when saving macros?

    Settings used:
    * WHATRECORD_MACRO_KEY_SKIP (str) - keys to skip, specified by regular
      expressions.  Should be valid Python syntax for a list of strings, as it
      will be handed to ``ast.literal_eval``.
    * WHATRECORD_MACRO_INCLUDE_ENV (bool) - serialize environment variables if
      set to 1.
    * WHATRECORD_MACRO_VALUE_MAX_LENGTH (int) - maximum length of macro values
      to serialize. 0 to disable maximum length check.

    Parameters
    ----------
    key : str
        The macro/environment variable name.
    value : str
        The value associated with the macro.

    Returns
    -------
    bool
    """
    # Above the maximum length threshold -> skip
    if settings.MACRO_VALUE_MAX_LENGTH > 0:
        if len(value) > settings.MACRO_VALUE_MAX_LENGTH:
            return False

    # Throw out environment variables if MACRO_INCLUDE_ENV is unset:
    if not settings.MACRO_INCLUDE_ENV and key in os.environ:
        return False

    # Bad key or one that matches regular expressions in RE_MACRO_KEY_SKIP
    # (by way of 'WHATRECORD_MACRO_KEY_SKIP')
    if not key:
        return False
    return not any(regex.fullmatch(key) for regex in RE_MACRO_KEY_SKIP)


@apischema.serializer
def _serialize_macro_context(ctx: MacroContext) -> Dict[str, Any]:
    macros = {
        key: value
        for key, value in ctx.items()
        if should_serialize_key(key, value)
    }

    return apischema.serialize(
        _SerializedMacroContext(
            show_warnings=ctx.show_warnings,
            string_encoding=ctx.string_encoding,
            macros=macros,
        )
    )


@apischema.deserializer
def _deserialize_macro_context(info: Dict[str, Any]) -> MacroContext:
    obj = apischema.deserialize(
        _SerializedMacroContext,
        info
    )
    return MacroContext(
        show_warnings=obj.show_warnings,
        string_encoding=obj.string_encoding,
        use_environment=False,
        macros=obj.macros,
    )


__all__ = ["MacroContext", "macros_from_string"]
