from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

import lark

from . import transformer
from .common import (AnyPath, FullLoadContext, ShellStateHandler,
                     StringWithContext)
from .db import PVAFieldReference, RecordInstance
from .iocsh import split_words
from .transformer import context_from_token


@dataclass
class SequencerProgram:
    """Representation of a state notation language (snl seq) program."""
    # variables: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_string(
        cls, contents: str, filename=None,
    ) -> SequencerProgram:
        """Load a state notation language file given its string contents."""
        comments = []
        grammar = lark.Lark.open_from_package(
            "whatrecord",
            "snl.lark",
            search_paths=("grammar", ),
            parser="lalr",
            lexer_callbacks={"COMMENT": comments.append},
        )

        proto = _ProgramTransformer(cls, filename).transform(
            grammar.parse(contents)
        )
        proto.comments = comments
        return proto

    @classmethod
    def from_file_obj(cls, fp, filename=None) -> SequencerProgram:
        """Load a state notation language program given a file object."""
        return cls.from_string(
            fp.read(),
            filename=getattr(fp, "name", filename),
        )

    @classmethod
    def from_file(cls, fn) -> SequencerProgram:
        """
        Load a state notation language file.

        Parameters
        ----------
        filename : pathlib.Path or str
            The filename.

        Returns
        -------
        program : SequencerProgram
            The parsed program.
        """
        with open(fn, "rt") as fp:
            return cls.from_string(fp.read(), filename=fn)


@lark.visitors.v_args(inline=True)
class _ProgramTransformer(lark.visitors.Transformer):
    def __init__(self, cls, fn, visit_tokens=False):
        super().__init__(visit_tokens=visit_tokens)
        self.fn = str(fn)
        self.cls = cls

    @lark.visitors.v_args(tree=True)
    def program(self, body):
        return body
