import dataclasses
from typing import Any, Dict

import apischema
from epicsmacrolib import MacroContext


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


@apischema.serializer
def _serialize_macro_context(ctx: MacroContext) -> Dict[str, Any]:
    return apischema.serialize(
        _SerializedMacroContext(
            show_warnings=ctx.show_warnings,
            string_encoding=ctx.string_encoding,
            macros=dict(ctx),
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
