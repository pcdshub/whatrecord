"""Helpers for writing lark transformers."""
from typing import Any, Optional, Tuple, TypeVar, Union

import lark

from .common import FullLoadContext, LoadContext


def context_from_token(fn: str, token: lark.Token) -> FullLoadContext:
    """Get a LoadContext from a lark Token."""
    return (LoadContext(name=fn, line=token.line), )


T = TypeVar("T")


@staticmethod
def tuple_args(*objects: T) -> Tuple[T, ...]:
    """Transformer helper to get back the *args tuple."""
    return objects


@staticmethod
def listify(*objects: Any):
    """Transformer helper to listify *args."""
    return list(objects)


@staticmethod
def listify_strings(*objects: Union[str, lark.Token]):
    """Transformer helper to listify *args and stringify each arg."""
    return list(str(obj) for obj in objects)


@staticmethod
def stringify(obj: lark.Token) -> str:
    """Transformer helper to stringify a single argument."""
    return str(obj)


@staticmethod
def pass_through(obj: Optional[T] = None) -> Optional[T]:
    """Transformer helper to pass through an optional single argument."""
    return obj


@staticmethod
def dictify(*tuples: Tuple[Any, Any]) -> dict:
    """Transformer helper to stringify a single argument."""
    return dict(tuples)


@staticmethod
def ignore(*args: Any) -> None:
    """Transformer helper to drop the subtree."""
