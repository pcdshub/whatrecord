import pytest

from ..iocsh import IocshRedirect, IocshSplit, split_words


@pytest.mark.parametrize(
    "line, expected",
    [
        pytest.param(
            """dbLoadRecords(a,  "b", "c")""",
            ["dbLoadRecords", "a", "b", "c"],
            id="basic_paren"
        ),
        pytest.param(
            """dbLoadRecords a,  "b", "c\"""",
            ["dbLoadRecords", "a", "b", "c"],
            id="basic_no_paren"
        ),
        pytest.param(
            """< input_file""",
            IocshSplit(
                [],
                redirects={
                    0: IocshRedirect(fileno=0, name="input_file", mode="r"),
                },
                error=None,
            ),
            id="basic_input_redirect",
        ),
        pytest.param(
            """> output_file""",
            IocshSplit(
                [],
                redirects={
                    1: IocshRedirect(fileno=1, name="output_file", mode="w"),
                },
                error=None,
            ),
            id="basic_output_redirect",
        ),
        pytest.param(
            """< input_file > output_file""",
            IocshSplit(
                [],
                redirects={
                    0: IocshRedirect(fileno=0, name="input_file", mode="r"),
                    1: IocshRedirect(fileno=1, name="output_file", mode="w"),
                },
                error=None,
            ),
            id="input_output_redirect",
        ),
        pytest.param(
            """2> output_file""",
            IocshSplit(
                [],
                redirects={
                    2: IocshRedirect(fileno=2, name="output_file", mode="w"),
                },
                error=None,
            ),
            id="output_fd_num",
        ),
        pytest.param(
            """test > stdout 2> stderr 3> whoknows""",
            IocshSplit(
                ["test"],
                redirects={
                    1: IocshRedirect(fileno=1, name="stdout", mode="w"),
                    2: IocshRedirect(fileno=2, name="stderr", mode="w"),
                    3: IocshRedirect(fileno=3, name="whoknows", mode="w"),
                },
                error=None,
            ),
            id="output_fd_num_more",
        ),
    ]
)
def test_split_words(line, expected):
    if isinstance(expected, list):
        expected = IocshSplit(
            argv=expected,
            redirects={},
            error=None,
        )
    assert split_words(line) == expected
