import pathlib
import pprint
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


snl_filenames = pytest.mark.parametrize(
    "program_filename",
    [
        pytest.param(
            program_filename,
            id="/".join(program_filename.parts[-2:])
        )
        for program_filename in SNL_FILES
    ]
)


@snl_filenames
def test_parse(program_filename):
    with open(program_filename, "rt") as fp:
        source = SequencerProgram.preprocess(
            fp.read(), search_path=program_filename.parent
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

    program = SequencerProgram.from_file(program_filename)

    # from ..format import FormatContext
    # ctx = FormatContext()
    # print(ctx.render_object(program, "console"))
    print(program)

    serialized = apischema.serialize(program)
    pprint.pprint(serialized)
    # apischema.deserialize(SequencerProgram, serialized)


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
