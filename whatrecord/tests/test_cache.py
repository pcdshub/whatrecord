from dataclasses import dataclass
from typing import Dict

from ..cache import Cached, CacheKey, InlineCached


def test_simple(tmp_path):
    @dataclass
    class TestKey(CacheKey):
        a: str
        b: int

    @dataclass
    class Test(Cached, key=TestKey, version=1, cache_path=tmp_path):
        a: str

    key = TestKey(a="a", b=2)
    obj1 = Test(key=key, a="1")
    assert obj1.save_to_cache()

    fn = key.to_filename(version=1, class_name="Test")
    assert (tmp_path / fn).exists()

    with open(tmp_path / fn) as fp:
        print("Cached data:")
        print(fp.read())

    obj2 = Test.from_cache(key)
    assert obj2 is not None
    print(obj1, obj2)
    assert obj1 == obj2


def test_dict_key():
    @dataclass
    class TestKey(CacheKey):
        a: dict
        b: int

    # dict key ordering shouldn't matter:
    key1 = TestKey(a={"a": 1, "b": 2}, b=2)
    key2 = TestKey(a={"b": 2, "a": 1}, b=2)
    assert key1.to_filename() == key2.to_filename()

    key3 = TestKey(a={"b": 2, "a": 1}, b=3)
    assert key3 != key1


def test_similar_keys():
    @dataclass
    class TestKey1(CacheKey):
        a: int
        b: int

    @dataclass
    class TestKey2(CacheKey):
        a: int
        b: int

    key1 = TestKey1(a=1, b=2)
    key2 = TestKey2(a=1, b=2)
    assert key1.to_filename() != key2.to_filename()


def test_identical_keys():
    @dataclass
    class TestKey1(CacheKey):
        a: int
        b: int

    @dataclass
    class TestKey2(CacheKey):
        a: int
        b: int

    key1 = TestKey1(a=1, b=2)
    key2 = TestKey2(a=1, b=2)

    # There's no way around this; so be careful with your CacheKey usage
    assert key1.to_filename(class_name="test") == key2.to_filename(class_name="test")


def test_simple_inline(tmp_path):
    @dataclass
    class TestKey(CacheKey):
        a: str
        b: int

    @dataclass
    class Test(InlineCached, TestKey, version=1, cache_path=tmp_path):
        ...

    key = TestKey(a="a", b=2)
    obj1 = Test(a="a", b=2)

    assert key.to_filename(class_name="Test") == obj1.to_filename()

    assert obj1.save_to_cache()

    fn = key.to_filename(version=1, class_name="Test")
    assert (tmp_path / fn).exists()

    with open(tmp_path / fn) as fp:
        print("Cached data:")
        print(fp.read())

    obj2 = Test.from_cache(key)
    assert obj2 is not None
    print("loaded from cache", obj2)
    assert obj1 == obj2


def test_inline_with_dataclass(tmp_path):
    @dataclass
    class Dependency:
        name: str

    @dataclass
    class TestKey(CacheKey):
        a: Dependency
        b: Dict[str, Dependency]

    @dataclass
    class Test(InlineCached, TestKey, version=1, cache_path=tmp_path):
        ...

    key = TestKey(a=Dependency(name="foo"), b={"c": Dependency(name="bar")})
    obj1 = Test(a=Dependency(name="foo"), b={"c": Dependency(name="bar")})

    assert key.to_filename(class_name="Test") == obj1.to_filename()

    assert obj1.save_to_cache()

    fn = key.to_filename(version=1, class_name="Test")
    assert (tmp_path / fn).exists()

    with open(tmp_path / fn) as fp:
        print("Cached data:")
        print(fp.read())

    obj2 = Test.from_cache(key)
    assert obj2 is not None
    print("loaded from cache", obj2)
    assert obj1 == obj2
