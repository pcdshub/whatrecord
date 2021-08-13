from __future__ import annotations

import inspect
import json
import logging
import pathlib
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, ClassVar, Mapping, Optional, Sequence, Type, TypeVar

import apischema

from whatrecord.common import AnyPath
from whatrecord.settings import CACHE_PATH
from whatrecord.util import get_bytes_sha256

T = TypeVar("T")


logger = logging.getLogger(__name__)


@dataclass
class CacheKey:
    def _to_cache_key_part(self, obj: Any) -> str:
        """Take an arbitrary value from the CacheKey and make a string out of it."""
        if is_dataclass(obj):
            obj = asdict(obj)
        if isinstance(obj, Mapping):
            return "_".join(self._to_cache_key_part(part) for part in sorted(obj.items()))
        if isinstance(obj, Sequence) and not isinstance(obj, (bytes, str)):
            return "_".join(self._to_cache_key_part(part) for part in obj)
        return repr(obj)

    def to_filename(self, version: int = 1, class_name: Optional[str] = None) -> str:
        """Get the cache filename."""
        def by_name(field):
            return field.name

        values = ":".join(
            field.name + "=" + self._to_cache_key_part(getattr(self, field.name))
            for field in sorted(fields(self), key=by_name)
        )
        value_repr = repr(values)
        sha = get_bytes_sha256(value_repr.encode("utf-8"))
        class_name = class_name or self.__class__.__name__
        return f"{class_name}_v{version}_{sha}.json"


_CacheKeyType = Type[CacheKey]


class _Cached:
    _cache_path_: ClassVar[Optional[pathlib.Path]]
    _cache_version_: ClassVar[int]
    CacheKey: ClassVar[_CacheKeyType]

    @classmethod
    def _get_cache_filename(cls, key: CacheKey):
        """Get the cache filename from the key."""
        filename = key.to_filename(class_name=cls.__name__, version=cls._cache_version_)
        return cls._cache_path_ / filename

    @classmethod
    def from_cache(cls: Type[T], key: CacheKey) -> Optional[T]:
        """Load the object based on its key from the whatrecord cache."""
        if cls is Cached:
            raise RuntimeError(f"Class {cls} is not intended to be saved/loaded")

        if cls._cache_path_ is None:
            return None

        try:
            with open(cls._get_cache_filename(key), "rb") as fp:
                serialized = json.load(fp)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError:
            logger.debug("Failed to deserialize %s %s", cls, key, exc_info=True)
            return None

        try:
            return apischema.deserialize(cls, serialized)
        except Exception:
            logger.debug("Failed to deserialize %s %s", cls, key, exc_info=True)
            return None

    def save_to_cache(self, pretty: bool = False, overwrite: bool = True) -> bool:
        """Save the object to the whatrecord cache."""
        if self._cache_path_ is None:
            return False

        filename = self._get_cache_filename(self.key)
        if filename.exists() and not overwrite:
            return False

        serialized = apischema.serialize(self)
        dump_args = {"indent": 4} if pretty else {}
        try:
            with open(filename, "wt") as fp:
                json.dump(serialized, fp, sort_keys=True, **dump_args)
        except Exception:
            logger.exception(
                "Failed to save %s(%s) to the cache. (filename = %s)",
                self.__class__.__name__, self.key,
                filename
            )
            return False

        return True


@dataclass
class Cached(_Cached):
    """
    A generic dataclass that can be cached in ``WHATRECORD_CACHE_PATH``.

    Expects to be subclassed and configured with a CacheKey subclass.
    """

    key: CacheKey = field(metadata=apischema.metadata.skip)

    def __init_subclass__(
        cls,
        key: Optional[_CacheKeyType] = None,
        version: int = 1,
        cache_path: Optional[AnyPath] = None,
    ):
        if key is None or not inspect.isclass(key) or not is_dataclass(key):
            raise RuntimeError(
                f"{cls.__name__} should be defined with a keyword argument 'key'; "
                f"such as `class {cls.__name__}(Cached, key=CacheKeyClass):"
            )

        cls._cache_version_ = version
        cls.__annotations__["key"] = key
        cls.CacheKey = key
        if cache_path is None and not CACHE_PATH:
            cls._cache_path_ = None  # cache disabled
        else:
            cls._cache_path_ = pathlib.Path(cache_path or CACHE_PATH)


@dataclass
class InlineCached(_Cached):
    """
    A generic dataclass that can be cached in ``WHATRECORD_CACHE_PATH``.

    Expects to be subclassed and mixed in with a CacheKey subclass.
    """

    def __init_subclass__(
        cls,
        version: int = 1,
        cache_path: Optional[AnyPath] = None,
    ):
        for supercls in cls.mro()[1:]:
            if issubclass(supercls, CacheKey) and supercls is not CacheKey:
                cls.CacheKey = supercls
                break
        else:
            raise RuntimeError(
                f"{cls.__name__} should be defined as a subclass of a CacheKey"
            )

        cls._cache_version_ = version
        if cache_path is None and not CACHE_PATH:
            cls._cache_path_ = None  # cache disabled
        else:
            cls._cache_path_ = pathlib.Path(cache_path or CACHE_PATH)

    @property
    def key(self) -> CacheKey:
        """An auto-generated CacheKey based on this dataclass's attributes."""
        kwargs = {
            field.name: getattr(self, field.name)
            for field in fields(self.CacheKey)
        }
        return self.CacheKey(**kwargs)
