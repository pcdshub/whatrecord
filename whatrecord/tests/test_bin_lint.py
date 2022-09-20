"""Tests for the 'whatrecord lint' subcommand."""

import os

import pytest

from ..bin.lint import main
from . import conftest

scripts_with_errors = {"ioc_failure", }


@conftest.startup_scripts
def test_load_no_errors(startup_script, capsys):
    if startup_script.parent.name in scripts_with_errors:
        pytest.skip(f"{startup_script.parent.name} is excluded from this test")

    os.environ["PWD"] = str(startup_script.resolve().parent)
    main(startup_script, verbosity=2)
    captured = capsys.readouterr()
    print("stdout:", captured.out)
    print("stderr:", captured.err)

    assert not captured.err
    assert "ERROR" not in captured.out
