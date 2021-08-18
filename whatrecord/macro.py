from typing import Dict

from _whatrecord.macro import MacroContext


def macros_from_string(
    macro_string: str, use_environment: bool = False
) -> Dict[str, str]:
    if not macro_string.strip():
        return {}
    macro_context = MacroContext(use_environment=use_environment)
    return macro_context.define_from_string(macro_string)


__all__ = ["MacroContext", "macros_from_string"]
