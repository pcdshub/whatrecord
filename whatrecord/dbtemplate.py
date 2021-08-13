"""dbLoadTemplate and msi -S substitution grammar helpers."""

from __future__ import annotations

import collections
import logging
import pathlib
import re
import shlex
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import apischema
import lark

from . import transformer
from .common import AnyPath, FullLoadContext
from .macro import MacroContext
from .transformer import context_from_token

logger = logging.getLogger(__name__)


def _strip_double_quote(value: str) -> str:
    """Strip one leading/single trailing double-quote."""
    if value[0] == '"':
        value = value[1:]
    if value[-1] == '"':
        value = value[:-1]
    return value


RE_REMOVE_ESCAPE = re.compile(r"\\(.)")


def _fix_value(value: str) -> str:
    """Remove quotes, and fix up escaping."""
    value = _strip_double_quote(value)
    return RE_REMOVE_ESCAPE.sub(r"\1", value)


@dataclass
class Substitution:
    """
    Single database template file from a full template.

    Represents approximately one line of a .substitutions file. For example,
    in this substitution file,

    ```
        file template.txt {
            pattern {a, b, c}
            {A, B, C}
        }
    ```

    The resulting Substitution would be

    ``Substitution(macros={"a": "A", "b": "B", "c": "C"}, filename="template.txt")``.

    Global macro values will be aggregated into this dictionary.

    Inside of the template file - ``template.txt`` above:
    * "include" is a supported command for the template file.
    * "substitute" is optionally supported (set ``allow_substitute``)
    """

    context: FullLoadContext
    filename: Optional[str] = None
    macros: Dict[str, str] = field(default_factory=dict)
    use_environment: bool = False
    allow_substitute: bool = True
    _items: Optional[List[Any]] = field(
        default_factory=list,
        metadata=apischema.metadata.skip,
    )

    def expand_file(
        self,
        *,
        filename: Optional[str] = None,
        search_paths: Optional[List[AnyPath]] = None
    ) -> str:
        """
        Expand the given file, looking in ``search_paths`` for template files.

        Parameters
        ----------
        filename : str, optional
            Expand this file or fall back to the instance-defined filename.

        search_paths : list of str or pathlib.Path, optional
            List of paths to search for template files.
        """
        filename = filename or self.filename
        if filename is None:
            raise ValueError("This substitution does not have a file defined")

        filename = pathlib.Path(filename)
        search_paths = search_paths or [filename.resolve().parent]
        with open(self.filename, "rt") as fp:
            return self.expand(fp.read(), search_paths=search_paths)

    @property
    def macro_context(self) -> MacroContext:
        """The macro context to be used when expanding the template."""
        ctx = MacroContext(use_environment=self.use_environment)
        ctx.define(**self.macros)
        return ctx

    @staticmethod
    def handle_include(filename: str, search_paths: List[AnyPath]) -> str:
        """Expand include files from the given search path."""
        for path in search_paths:
            option = pathlib.Path(path) / filename
            if option.exists():
                with open(option, "rt") as fp:
                    return fp.read()

        friendly_paths = " or ".join(f'"{path}"' for path in search_paths)
        raise FileNotFoundError(f"{filename} not found in {friendly_paths}")

    def expand(self, source: str, search_paths: Optional[List[AnyPath]] = None):
        """
        Expand the provided substitution template, using the macro environment.

        Parameters
        ----------
        source : str
            The source substitution template.  May contain "include" or
            "substitute" lines.

        search_paths : list of str or pathlib.Path, optional
            List of paths to search for template files.
        """
        ctx = self.macro_context
        search_paths = search_paths or [pathlib.Path(".")]
        results = []
        source_stack = collections.deque(source.splitlines())
        while source_stack:
            line = source_stack.popleft()
            logger.debug("line %r", line)
            line = ctx.expand(line)
            command, *command_args = line.strip().split(" ", 1)
            if command == "include":  # case sensitive
                args = shlex.split(command_args[0])
                if len(args) != 1:
                    raise ValueError(
                        f"Include command takes one argument; got: {args} "
                        f"where line={line!r}"
                    )
                include_file = args[0]
                logger.debug("Including file from %s", include_file)
                include_source = self.handle_include(include_file, search_paths)
                source_stack.extendleft(reversed(include_source.splitlines()))
                logger.debug("stack %r", source_stack)
            elif command == "substitute" and self.allow_substitute:
                # Note that dbLoadTemplate does not support substitute, but msi
                # does.
                macro_string = command_args[0].strip()
                # Strip only single beginning and end quotes
                macro_string = _strip_double_quote(macro_string).strip()
                logger.debug("Substituting additional macros %s", macro_string)
                ctx.define_from_string(macro_string)
            else:
                results.append(line)

        return "\n".join(results)


@dataclass
class VariableDefinitions:
    """Variable definitions."""

    context: FullLoadContext
    definitions: Dict[str, str] = field(default_factory=dict)


@dataclass
class GlobalDefinitions(VariableDefinitions):
    """Global variable definitions."""


@dataclass
class PatternHeader:
    """Pattern header."""

    context: FullLoadContext
    patterns: List[str]


@dataclass
class PatternValues:
    """Pattern values."""

    context: FullLoadContext
    values: List[str]


@dataclass
class TemplateSubstitution:
    """Database substitutions, containing zero or more template files."""

    substitutions: List[Substitution] = field(default_factory=list)

    def expand_template(
        self,
        template: str,
        search_paths: Optional[List[AnyPath]] = None,
        delimiter: str = "\n",
    ) -> str:
        """
        Expands all substitutions for the given string.

        Parameters
        ----------
        template : str
            The template text.

        delimiter : str, optional
            Delimiter to join individual substitutions.

        search_paths : list of str or pathlib.Path, optional
            List of paths to search for template files.
        """
        return delimiter.join(
            sub.expand(template, search_paths=search_paths)
            for sub in self.substitutions
        )

    def expand_files(
        self,
        search_paths: Optional[List[AnyPath]] = None,
        delimiter: str = "\n"
    ) -> str:
        """
        Expands and combines all contained substitution files.

        Parameters
        ----------
        delimiter : str, optional
            Delimiter to join individual substitutions.

        search_paths : list of str or pathlib.Path, optional
            List of paths to search for template files.
        """
        return delimiter.join(
            sub.expand_file(search_paths=search_paths)
            for sub in self.substitutions
        )

    @classmethod
    def from_string(
        cls,
        contents,
        filename=None,
        msi_format=False,
        all_global_scope=False,
    ) -> TemplateSubstitution:
        """Load a template substitutions file given its string contents."""
        comments = []
        grammar_filename = "msi-sub.lark" if msi_format else "dbtemplate.lark"

        grammar = lark.Lark.open_from_package(
            "whatrecord",
            grammar_filename,
            search_paths=("grammar",),
            parser="earley",
            lexer_callbacks={"COMMENT": comments.append},
            propagate_positions=True,
        )

        if msi_format:
            tr = _TemplateMsiTransformer(
                cls, filename, all_global_scope=all_global_scope
            )
        else:
            tr = _TemplateTransformer(cls, filename)

        subs = tr.transform(grammar.parse(contents))
        subs.comments = comments
        return subs

    @classmethod
    def from_file_obj(cls, fp, filename=None) -> TemplateSubstitution:
        """Load a template file given a file object."""
        return cls.from_string(
            fp.read(),
            filename=getattr(fp, "name", filename),
        )

    @classmethod
    def from_file(cls, fn) -> TemplateSubstitution:
        """
        Load a template file.

        Parameters
        ----------
        filename : pathlib.Path or str
            The filename.

        Returns
        -------
        template : TemplateSubstitution
            The template file.
        """
        with open(fn, "rt") as fp:
            return cls.from_string(fp.read(), filename=fn)


@lark.visitors.v_args(inline=True)
class _TemplateMsiTransformer(lark.visitors.Transformer):
    _allow_substitute = True

    def __init__(self, cls, fn, visit_tokens=False, all_global_scope=False):
        super().__init__(visit_tokens=visit_tokens)
        self.fn = str(fn)
        self._template = cls()
        self._stack = []
        self._globals = {}
        self.all_global_scope = all_global_scope

    @lark.visitors.v_args(tree=True)
    def msi_substitutions(self, *_):
        self._template.substitutions = self._squash_stack(self._stack)
        return self._template

    template_filename = transformer.stringify
    pattern_name = transformer.stringify
    pattern_value = transformer.pass_through
    pattern_names = transformer.tuple_args
    variable_substitutions = transformer.tuple_args
    variable_definition = transformer.tuple_args
    variable_definitions = transformer.dictify

    def global_definitions(self, global_token: lark.Token, variable_definitions=None):
        self._stack.append(
            GlobalDefinitions(
                context=context_from_token(self.fn, global_token),
                definitions=dict(
                    (str(key), str(value))
                    for key, value in (variable_definitions or {}).items()
                ),
            )
        )

    def variable_subs(self, variable_definitions):
        token = list(variable_definitions)[0]
        definitions = VariableDefinitions(
            context=context_from_token(self.fn, token),
            definitions=dict(
                (str(key), _fix_value(value))
                for key, value in (variable_definitions or {}).items()
            ),
        )
        self._stack.append(definitions)
        return definitions

    def pattern_header(self, pattern_token: lark.Token, *values):
        header = PatternHeader(
            context=context_from_token(self.fn, pattern_token),
            patterns=list(_fix_value(value) for value in values),
        )
        self._stack.append(header)
        return header

    def pattern_values(self, *values):
        pattern_values = PatternValues(
            context=context_from_token(self.fn, values[0]),
            values=list(_fix_value(value) for value in values),
        )
        self._stack.append(pattern_values)
        return pattern_values

    @lark.visitors.v_args(tree=True)
    def empty(self, tree):
        empty = PatternValues(
            context=context_from_token(self.fn, tree),
            values=[],
        )
        self._stack.append(empty)
        return empty

    def dbfile(self, file_token: lark.Token, filename: str, *fields):
        stack = self._stack
        file = Substitution(
            context=context_from_token(self.fn, file_token),
            filename=str(pathlib.Path(self.fn).parent / _strip_double_quote(filename)),
            allow_substitute=self._allow_substitute,
            _items=stack,
        )
        self._stack = [file]
        return file

    def _squash_stack(self, stack):
        patterns = []
        results = []
        for item in stack:
            if isinstance(item, Substitution):
                item_stack = item._items
                item._items = None
                subs = self._squash_stack(item_stack)
                for sub in subs:
                    sub.filename = item.filename
                results.extend(subs)
            elif isinstance(item, PatternHeader):
                patterns = item.patterns
            elif isinstance(item, PatternValues):
                values = dict(self._globals)
                pattern_dict = dict(zip(patterns, item.values))
                values.update(pattern_dict)
                results.append(
                    Substitution(
                        context=item.context,
                        filename=None,
                        macros=values,
                        allow_substitute=self._allow_substitute,
                        # fields=patterns,
                        # instances=values,
                    )
                )
            elif isinstance(item, GlobalDefinitions):
                self._globals.update(item.definitions)
            elif isinstance(item, VariableDefinitions):
                values = dict(self._globals)
                values.update(item.definitions)
                if self.all_global_scope:
                    self._globals.update(item.definitions)
                results.append(
                    Substitution(
                        context=item.context,
                        filename=None,
                        macros=values,
                        allow_substitute=self._allow_substitute,
                        # fields=patterns,
                        # instances=values,
                    )
                )

        return results


@lark.visitors.v_args(inline=True)
class _TemplateTransformer(_TemplateMsiTransformer):
    _allow_substitute = False

    @lark.visitors.v_args(tree=True)
    def substitution_file(self, *_):
        self._template.substitutions = self._squash_stack(self._stack)
        return self._template

    pattern_substitutions = transformer.tuple_args
    substitutions = transformer.tuple_args
