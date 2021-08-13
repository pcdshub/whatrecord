import pytest

from .. import common
from ..common import LoadContext


@pytest.mark.parametrize(
    "ctx, expected",
    [
        pytest.param(
            (LoadContext("a", 0), LoadContext("a", 10), LoadContext("c", 1)),
            (LoadContext("a", 10), LoadContext("c", 1)),
            id="redundant",
        ),
        pytest.param(
            (LoadContext("a", 1), LoadContext("a", 10), LoadContext("c", 1)),
            (LoadContext("a", 1), LoadContext("a", 10), LoadContext("c", 1)),
            id="not-redundant",
        ),
        pytest.param((), (), id="empty"),
    ]
)
def test_redundant_context(ctx, expected):
    assert common.remove_redundant_context(ctx) == expected
