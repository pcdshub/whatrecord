import pathlib
# import pprint
import textwrap

import apischema
import pytest

from ..snl import SequencerProgram
from . import conftest

SNL_FILES = list((conftest.MODULE_PATH / "iocs").glob("**/*.st"))

additional_files = conftest.MODULE_PATH / "sequencer_filenames.txt"
if additional_files.exists():
    for additional in open(additional_files, "rt").read().splitlines():
        SNL_FILES.append(pathlib.Path(additional))


SNL_IDS = [
    "/".join(program_filename.parts[-2:])
    for program_filename in SNL_FILES
]


@pytest.fixture(
    params=SNL_FILES,
    ids=SNL_IDS,
)
def snl_filename(request) -> pathlib.Path:
    return request.param


@pytest.fixture
def snl_program(snl_filename) -> SequencerProgram:
    with open(snl_filename, "rt") as fp:
        source = SequencerProgram.preprocess(
            fp.read(), search_path=snl_filename.parent
        )
    has_program = any(
        line.startswith("program")
        for line in source.splitlines()
    )
    if not has_program:
        raise pytest.skip(
            "No program found in source "
            "(perhaps it's meant to be included from another?)"
        )

    return SequencerProgram.from_file(snl_filename)


def test_parse(snl_program: SequencerProgram):
    # from ..format import FormatContext
    # ctx = FormatContext()
    # print(ctx.render_object(program, "console"))
    print(snl_program)

    serialized = apischema.serialize(snl_program)
    # pprint.pprint(serialized)
    apischema.deserialize(SequencerProgram, serialized)
    # deserialized = apischema.deserialize(SequencerProgram, serialized)
    # assert deserialized == snl_program

    round_trip = str(snl_program)
    print("Round-tripped to")
    print(round_trip)
    assert "(context=(" not in round_trip
    assert "(Tree=(" not in round_trip
    assert "(Token=(" not in round_trip


def test_graph(snl_filename: pathlib.Path, snl_program: SequencerProgram):
    graph = snl_program.as_graph()
    digraph = graph.to_digraph()

    from ..bin.graph import render_graph_to_file
    render_graph_to_file(digraph, filename=f"{snl_filename}.pdf")


@pytest.mark.parametrize(
    "source, partial_error",
    [
        pytest.param(
            """\
            program name
            #define VALUE 5

            double a[VALUE];

            ss simple {
                state simple {
                    when () {} exit
                }
            }
            """,
            "No terminal matches 'V' in the current parser context",
            id="preprocessor_define"
        ),
        pytest.param(
            """\
            program name
            #define DEFINED 1

            #if DEFINED
            #else
            !!! invalid syntax
            #endif
            double a[VALUE];

            ss simple {
                state simple {
                    when () {} exit
                }
            }
            """,
            "No terminal matches '!' in the current parser context",
            id="preprocessor_define"
        ),
    ]
)
@pytest.mark.xfail(strict=True, reason="preprocessor incomplete")
def test_tofix(source, partial_error):
    source = textwrap.dedent(source)
    try:
        SequencerProgram.from_string(source)
    except Exception as ex:
        if partial_error in str(ex):
            raise
        print(ex)
