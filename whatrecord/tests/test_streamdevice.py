import pathlib
import pprint

import apischema
import pytest

from ..streamdevice import StreamProtocol
from . import conftest

PROTOCOL_FILES = list((conftest.MODULE_PATH / "iocs").glob("**/*.proto"))

additional_files = conftest.MODULE_PATH / "streamdevice_filenames.txt"
if additional_files.exists():
    for additional in open(additional_files, "rt").read().splitlines():
        PROTOCOL_FILES.append(pathlib.Path(additional))


protocol_files = pytest.mark.parametrize(
    "protocol_file",
    [
        pytest.param(
            protocol_file,
            id="/".join(protocol_file.parts[-2:])
        )
        for protocol_file in PROTOCOL_FILES
    ]
)


@protocol_files
def test_parse(protocol_file):
    proto = StreamProtocol.from_file(protocol_file)

    serialized = apischema.serialize(proto)
    pprint.pprint(serialized)
    apischema.deserialize(StreamProtocol, serialized)
