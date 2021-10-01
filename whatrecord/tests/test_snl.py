import pathlib

# import apischema
import pytest

from ..snl import SequencerProgram
from . import conftest

# import pprint


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
    program = SequencerProgram.from_file(program_filename)
    print(program.pretty())

    # serialized = apischema.serialize(program)
    # pprint.pprint(serialized)
    # apischema.deserialize(SequencerProgram, serialized)
