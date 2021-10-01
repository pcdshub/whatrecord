from __future__ import annotations

import collections
import pathlib
import shlex
from dataclasses import dataclass
from typing import Optional

import lark

from .common import AnyPath

# from . import transformer
# from .common import (AnyPath, FullLoadContext, ShellStateHandler,
#                      StringWithContext)
# from .db import RecordInstance
# from .transformer import context_from_token


@dataclass
class SequencerProgram:
    """Representation of a state notation language (snl seq) program."""
    # variables: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    def preprocess(code: str, search_path: Optional[AnyPath] = None) -> str:
        """Preprocess the given sequencer code, expanding #include."""
        # Line numbers will be off with this, sadly
        # The sequencer itself gets around this by using LINE_MARKER tokens
        # to indicate what file and line the code came from.  This could
        # be something we support in the future, but it might not be easy
        # with lark...
        search_path = pathlib.Path("." if search_path is None else search_path)
        result = []
        stack = collections.deque(
            [
                (search_path, line)
                for line in code.splitlines()
            ]
        )
        while stack:
            search_path, line = stack.popleft()
            if line.startswith("#include"):
                _, include_file, *_ = shlex.split(line)
                include_file = (search_path / include_file).resolve()
                with open(include_file, "rt") as fp:
                    stack.extendleft(
                        [
                            (include_file.parent, line)
                            for line in reversed(fp.read().splitlines())
                        ]
                    )
            elif line.startswith("#if"):
                ...  # sorry; this may break things
            elif line.startswith("#else"):
                ...  # sorry; this may break things
            elif line.startswith("#elif"):
                ...  # sorry; this may break things
            elif line.startswith("#endif"):
                ...  # sorry; this may break things
            elif line.startswith("#define"):
                ...  # sorry; I think we can do better
            else:
                result.append(line)

        print("\n".join(result))
        return "\n".join(result)

    @classmethod
    def from_string(
        cls,
        contents: str,
        filename: Optional[AnyPath] = None,
    ) -> SequencerProgram:
        """Load a state notation language file given its string contents."""
        comments = []
        grammar = lark.Lark.open_from_package(
            "whatrecord",
            "snl.lark",
            search_paths=("grammar", ),
            parser="earley",
            lexer_callbacks={"COMMENT": comments.append},
        )

        search_path = None
        if filename:
            search_path = pathlib.Path(filename).resolve().parent

        preprocessed = cls.preprocess(contents, search_path=search_path)
        proto = _ProgramTransformer(cls, filename).transform(
            grammar.parse(preprocessed)
        )
        proto.comments = comments
        return proto

    @classmethod
    def from_file_obj(cls, fp, filename: Optional[AnyPath] = None) -> SequencerProgram:
        """Load a state notation language program given a file object."""
        return cls.from_string(
            fp.read(),
            filename=getattr(fp, "name", filename),
        )

    @classmethod
    def from_file(cls, fn: AnyPath) -> SequencerProgram:
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
