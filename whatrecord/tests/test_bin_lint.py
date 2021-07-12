"""Tests for the 'whatrecord lint' subcommand."""

import os

from ..bin.lint import main
from . import conftest


@conftest.startup_scripts
def test_load_no_errors(startup_script, capsys):
    os.environ["PWD"] = str(startup_script.resolve().parent)
    main(startup_script, verbosity=2)
    captured = capsys.readouterr()
    print("stdout:", captured.out)
    print("stderr:", captured.err)

    assert not captured.err
    assert "ERROR" not in captured.out
