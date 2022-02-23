from __future__ import annotations

import collections
import logging
import pathlib
import shlex
import textwrap
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Union

import graphviz as gv
import lark

from . import transformer
from .common import AnyPath, FullLoadContext
from .graph import _GraphHelper
from .transformer import context_from_token

logger = logging.getLogger(__name__)


@dataclass
class Definition:
    context: FullLoadContext


@dataclass
class Expression:
    context: FullLoadContext


@dataclass
class CommaSeparatedExpressions(Expression):
    expressions: List[Expression]

    def __str__(self) -> str:
        return ", ".join(str(item) for item in self.expressions)


OptionalExpression = Optional[Union[Expression, CommaSeparatedExpressions]]


@dataclass
class Assignment(Definition):
    variable: str
    value: Optional[Union[str, Sequence[str]]] = None
    subscript: Optional[str] = None

    def __str__(self) -> str:
        if isinstance(self.value, tuple):
            value = "{ " + ", ".join(str(s) for s in self.value) + "}"
        else:
            value = str(self.value)
        return f"{self.variable}{self.subscript or ''} = {value};"


@dataclass
class AbstractDeclarator:
    context: FullLoadContext
    params: Sequence[ParameterDeclarator] = field(default_factory=list)
    modifier: Optional[str] = None
    subscript: Optional[int] = None

    def __str__(self) -> str:
        raise NotImplementedError("TODO: abstractdeclarator cleanup")
        # params = ", ".join(str(param) for param in self.params)
        # return f"({params})"


@dataclass
class Type:
    context: FullLoadContext
    name: str
    abstract: Optional[AbstractDeclarator] = None

    def __str__(self) -> str:
        return f"{self.abstract or ''}{self.name}"


@dataclass
class Monitor(Definition):
    variable: str
    subscript: Optional[int]

    def __str__(self) -> str:
        return f"monitor {self.variable}{self.subscript or ''};"


@dataclass
class Option(Definition):
    name: str
    enable: bool

    def __str__(self) -> str:
        plus = "+" if self.enable else "-"
        return f"option {plus}{self.name};"


@dataclass
class Sync(Definition):
    variable: str
    subscript: Optional[int]
    queued: bool
    event_flag: Optional[str] = None
    queue_size: Optional[int] = None

    def __str__(self) -> str:
        subscript = str(self.subscript or "")
        variable = f"{self.variable}{subscript}"
        event_flag = f" to {self.event_flag}" if self.event_flag else ""
        if self.queued:
            return f"syncq {variable}{event_flag} {self.queue_size or ''};"

        return f"sync {variable}{event_flag};"


@dataclass
class Declaration(Definition):
    type: Optional[Type] = None
    declarators: Optional[Sequence[Declarator]] = field(default_factory=list)

    def __str__(self) -> str:
        declarators = ", ".join(str(decl) for decl in self.declarators or [])
        return f"{self.type} {declarators};"


@dataclass
class ForeignDeclaration(Declaration):
    names: Sequence[str] = field(default_factory=list)

    def __str__(self) -> str:
        names = ", ".join(self.names)
        return f"foreign {names};"


@dataclass
class Declarator:
    context: FullLoadContext
    object: Union[Declarator, Variable]
    params: Optional[List[ParameterDeclarator]] = None
    value: Optional[Expression] = None
    modifier: Optional[str] = None
    subscript: Optional[int] = None

    def __str__(self) -> str:
        if self.modifier == "()":
            decl = f"({self.object})"
        elif self.modifier:
            decl = f"{self.modifier}{self.object}"
        elif self.subscript:
            decl = f"{self.object}{self.subscript}"
        elif self.params:
            params = ", ".join(str(param) for param in self.params)
            decl = f"{self.object}({params})"
        else:
            decl = str(self.object)
        if self.value:
            return f"{decl} = {self.value}"
        return f"{decl}"


@dataclass
class ParameterDeclarator:
    context: FullLoadContext
    type: Type
    declarator: Optional[Declarator] = None

    def __str__(self) -> str:
        if self.declarator:
            return f"{self.type} {self.declarator}"
        return str(self.type)


@dataclass
class State:
    context: FullLoadContext
    name: str
    definitions: Sequence[Definition] = field(default_factory=list)
    transitions: Sequence[Transition] = field(default_factory=list)
    entry: Optional[Block] = None
    exit: Optional[Block] = None
    code_transitions: List[StateStatement] = field(default_factory=list)

    def __str__(self) -> str:
        definitions = "\n".join(
            str(defn)
            for defn in self.definitions
        )
        transitions = "\n".join(
            str(transition)
            for transition in self.transitions
        )
        return "\n".join(
            line for line in (
                f"state {self.name}" + " {",
                str(self.entry or ""),
                textwrap.indent(definitions, " " * 4),
                textwrap.indent(transitions, " " * 4),
                str(self.exit or ""),
                "}",
            )
            if line
        )


@dataclass
class StateSet:
    context: FullLoadContext
    name: str
    definitions: Sequence[Definition] = field(default_factory=list)
    states: Sequence[State] = field(default_factory=list)

    def __str__(self) -> str:
        definitions = "\n".join(
            str(defn)
            for defn in self.definitions
        )
        states = "\n".join(
            str(state)
            for state in self.states
        )
        return "\n".join(
            (
                f"ss {self.name}" + " {",
                textwrap.indent(definitions, " " * 4),
                textwrap.indent(states, " " * 4),
                "}",
            )
        )


@dataclass
class Transition:
    context: FullLoadContext
    block: Block
    target_state: Optional[str] = None
    condition: OptionalExpression = None

    def __str__(self) -> str:
        state = (
            f"state {self.target_state}"
            if self.target_state
            else
            "exit"
        )
        return "\n".join(
            line for line in (
                f"when ({self.condition or ''})" + " {",
                str(self.block),
                "}" + f" {state}",
            )
            if line
        )


@dataclass
class ExitTransition(Transition):
    ...


@dataclass
class Block:
    context: FullLoadContext
    definitions: Sequence[Definition] = field(default_factory=list)
    statements: Sequence[Statement] = field(default_factory=list)

    def __str__(self) -> str:
        definitions = textwrap.indent(
            "\n".join(
                str(defn)
                for defn in self.definitions
            ),
            prefix="    ",
        )
        statements = textwrap.indent(
            "\n".join(
                str(statement)
                for statement in self.statements
            ),
            prefix="    ",
        )
        return "\n".join(
            (
                "{",
                definitions,
                statements,
                "}",
            )
        )


@dataclass
class Statement:
    context: FullLoadContext


@dataclass
class BreakStatement(Statement):
    def __str__(self) -> str:
        return "break;"


@dataclass
class ContinueStatement(Statement):
    def __str__(self) -> str:
        return "continue;"


@dataclass
class ReturnStatement(Statement):
    value: Optional[Expression] = None

    def __str__(self) -> str:
        if self.value is not None:
            return f"return {self.value};"
        return "return;"


@dataclass
class StateStatement(Statement):
    name: str

    def __str__(self) -> str:
        return f"state {self.name};"


@dataclass
class WhileStatement(Statement):
    condition: CommaSeparatedExpressions
    body: Statement

    def __str__(self) -> str:
        return f"while ({self.condition}) " + str(self.body).lstrip()


@dataclass
class ForStatement(Statement):
    init: OptionalExpression
    condition: OptionalExpression
    increment: OptionalExpression
    statement: Statement

    def __str__(self) -> str:
        return (
            f"for ({self.init or ''}; {self.condition or ''}; {self.increment or ''}) " +
            str(self.statement).lstrip()
        )


@dataclass
class ExpressionStatement(Statement):
    expression: CommaSeparatedExpressions

    def __str__(self) -> str:
        return f"{self.expression};"


@dataclass
class IfStatement(Statement):
    condition: CommaSeparatedExpressions
    body: Statement
    else_body: Optional[Statement] = None

    def __str__(self) -> str:
        else_clause = "\n".join(
            (
                "\nelse {",
                textwrap.indent(str(self.else_body), " " * 4),
                "}",
            )
            if self.else_body else ""
        )

        return "\n".join(
            (
                f"if ({self.condition}) " + " {",
                textwrap.indent(str(self.body), " " * 4),
                else_clause,
                "}",
            )
        )


@dataclass
class FuncDef(Definition):
    type: Type
    declarator: Declarator
    block: Block

    def __str__(self) -> str:
        return f"{self.type} {self.declarator};"


@dataclass
class StructMemberDecl:
    context: FullLoadContext
    type: Type
    declarator: Declarator

    def __str__(self) -> str:
        return f"{self.type} {self.declarator};"


@dataclass
class CCode(Definition):
    code: str

    def __str__(self) -> str:
        return self.code


@dataclass
class StructDef(Definition):
    name: str
    members: Sequence[Union[StructMemberDecl, CCode]] = field(default_factory=list)

    def __str__(self) -> str:
        members = "\n".join(
            str(member) for member in self.members
        )
        return "\n".join(
            (
                f"struct {self.name}" + " {",
                textwrap.indent(members, " " * 4),
                "}",
            )
        )


@dataclass
class Variable(Expression):
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass
class InitExpression(Expression):
    """
    Of the form:
        ( type ) { init_exprs }
        { init_exprs }
        expr
    """

    # TODO: may be improved?
    context: FullLoadContext
    expressions: Sequence[Union[InitExpression, Expression]] = field(
        default_factory=list
    )
    type: Optional[Type] = None

    def __str__(self) -> str:
        exprs = ", ".join(str(expr or '') for expr in self.expressions)
        type_prefix = f"({self.type}) " if self.type else ""
        return f"{type_prefix}{{ {exprs} }}"


@dataclass
class Literal(Expression):
    type: str
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass
class UnaryPrefixExpression(Expression):
    operator: str
    expression: Expression

    def __str__(self) -> str:
        return f"{self.operator}{self.expression}"


@dataclass
class UnaryPostfixExpression(Expression):
    expression: Expression
    operator: str

    def __str__(self) -> str:
        return f"{self.expression}{self.operator}"


@dataclass
class BinaryOperatorExpression(Expression):
    left: Expression
    operator: str
    right: Expression

    def __str__(self) -> str:
        return f"{self.left} {self.operator} {self.right}"


@dataclass
class TypeCastExpression(Expression):
    type: Type
    expression: Expression

    def __str__(self) -> str:
        return f"{self.type}({self.expression})"


@dataclass
class TernaryExpression(Expression):
    condition: Expression
    if_true: Expression
    if_false: Expression

    def __str__(self) -> str:
        return f"{self.condition} ? {self.if_true} : {self.if_false}"


@dataclass
class MemberExpression(Expression):
    parent: Expression
    member: str
    dereference: bool  # True = ->, False = .

    def __str__(self) -> str:
        if self.dereference:
            return f"{self.parent}->{self.member}"
        return f"{self.parent}.{self.member}"


@dataclass
class SizeofExpression(Expression):
    type: Type

    def __str__(self) -> str:
        return f"sizeof({self.type})"


@dataclass
class ExitExpression(Expression):
    args: OptionalExpression

    def __str__(self) -> str:
        return f"exit({self.args or ''})"


@dataclass
class BracketedExpression(Expression):
    outer: Expression
    inner: Expression

    def __str__(self) -> str:
        return f"{self.outer}[{self.inner}]"


@dataclass
class ParenthesisExpression(Expression):
    expression: Expression

    def __str__(self) -> str:
        return f"({self.expression})"


@dataclass
class ExpressionWithArguments(Expression):
    expression: Expression
    arguments: OptionalExpression = None

    def __str__(self) -> str:
        return f"{self.expression}({self.arguments or ''})"


class SequencerProgramGraph(_GraphHelper):
    """
    A graph for a SequencerProgram.

    Parameters
    ----------
    program : SequencerProgram, optional
        A program to add.

    highlight_states : list of str, optional
        List of state names to highlight.

    include_code : bool, optional
        Include code, where relevant, in nodes.
    """

    _entry_label: str = "_Entry_"
    _exit_label: str = "_Exit_"

    def __init__(
        self,
        program: Optional[SequencerProgram] = None,
        highlight_states: Optional[List[str]] = None,
        include_code: bool = False,
    ):
        super().__init__()
        self.include_code = include_code
        self.highlight_states = highlight_states or []
        if program is not None:
            self.add_program(program)

    def add_program(self, program: SequencerProgram):
        """Add a program to the graph."""
        for state_set in program.state_sets:
            for state in state_set.states:
                self._add_state(program, state_set, state)

        # Only add entry/exit labels if there's an edge
        if self._entry_label in self.nodes:
            self.get_node(
                self._entry_label,
                self.get_code(program.entry, "(Startup)")
            )

        if self._exit_label in self.nodes:
            self.get_node(
                self._exit_label,
                self.get_code(program.exit, "(Exit)")
            )

    def _add_state(self, program: SequencerProgram, state_set: StateSet, state: State):
        """Add a state set's state to the graph."""
        qualified_name = f"{state_set.name}.{state.name}"
        self.get_node(
            qualified_name,
            text="\n".join(self._get_state_node_text(state_set, state)),
        )

        if state_set.states[0] is state:
            self.add_edge(
                self._entry_label,
                qualified_name,
            )

        for transition in state.transitions:
            self._add_transition(program, state_set, state, transition)

        for transition in state.code_transitions:
            self.add_edge(
                qualified_name,
                f"{state_set.name}.{transition.name}",
                label=f"(Line {transition.context[-1].line})",
            )

    def to_digraph(
        self,
        graph: Optional[gv.Digraph] = None,
        engine: str = "dot",
        font_name: Optional[str] = "Courier",
        format: str = "pdf",
    ) -> gv.Digraph:
        """
        Create a graphviz digraph.

        Parameters
        ----------
        graph : graphviz.Graph, optional
            Graph instance to use.  New one created if not specified.
        engine : str, optional
            Graphviz engine (dot, fdp, etc).
        font_name : str, optional
            Font name to use for all nodes and edges.
        format :
            The output format used for rendering (``'pdf'``, ``'png'``, ...).
        """
        for node in self.nodes.values():
            node.highlighted = node.label in self.highlight_states
        return super().to_digraph(
            graph=graph, engine=engine, font_name=font_name, format=format
        )

    def _add_transition(
        self,
        program: SequencerProgram,
        state_set: StateSet,
        state: State,
        transition: Transition,
    ):
        """Add a state set's state transition to the graph."""
        state_qualified_name = f"{state_set.name}.{state.name}"
        label = str(transition.condition or "")
        transition_text = self.get_code(transition.block)
        target_state = (
            f"{state_set.name}.{transition.target_state}"
            if transition.target_state
            else self._exit_label
        )
        if not self.include_code or not transition_text:
            self.add_edge(state_qualified_name, target_state, label=label)
            return

        transition_idx = state.transitions.index(transition)
        transition_node = f"{state_qualified_name}.{transition_idx}"
        self.get_node(transition_node, text=transition_text)
        self.add_edge(state_qualified_name, transition_node, label=label)
        self.add_edge(transition_node, target_state)

    def get_code(self, obj, default: str = ""):
        """Get code for a node/edge."""
        if self.include_code and obj is not None:
            return self.clean_code(str(obj)) or default
        return default

    def _get_state_node_text(self, state_set: StateSet, state: State):
        yield f"<b>{state_set.name}.{state.name}</b>"
        if self.include_code:
            if state.entry is not None:
                yield "<u>Entry</u>"
                yield self.clean_code(state.entry)
            if state.exit is not None:
                yield "<u>Exit</u>"
                yield self.clean_code(state.exit)


@dataclass
class SequencerProgram:
    """Representation of a state notation language (snl seq) program."""

    context: FullLoadContext
    name: str
    params: Optional[str]
    initial_definitions: Sequence[Definition] = field(default_factory=list)
    entry: Optional[Block] = None
    state_sets: Sequence[StateSet] = field(default_factory=list)
    exit: Optional[Block] = None
    final_definitions: Sequence[Definition] = field(default_factory=list)

    def __str__(self) -> str:
        initial_definitions = "\n".join(
            str(defn)
            for defn in self.initial_definitions
        )
        final_definitions = "\n".join(
            str(defn)
            for defn in self.final_definitions
        )
        state_sets = "\n\n".join(
            str(state_set)
            for state_set in self.state_sets
        )
        param = f"({self.params})" if self.params else ""
        return "\n\n".join(
            line for line in (
                f"program {self.name}{param}",
                initial_definitions,
                str(self.entry or ""),
                state_sets,
                str(self.exit or ""),
                final_definitions,
            )
            if line
        )

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
        stack = collections.deque([(search_path, line) for line in code.splitlines()])
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
                while stack and line.endswith("\\"):
                    search_path, line = stack.popleft()

                ...  # sorry; I think we can do better
            else:
                result.append(line)

        return "\n".join(result)

    @classmethod
    def from_string(
        cls,
        contents: str,
        filename: Optional[AnyPath] = None,
        debug: bool = False,
    ) -> SequencerProgram:
        """Load a state notation language file given its string contents."""
        comments = []
        grammar = lark.Lark.open_from_package(
            "whatrecord",
            "snl.lark",
            search_paths=("grammar",),
            parser="earley",
            # TODO: alternative comment finding method
            # lexer_callbacks={"COMMENT": comments.append},
            maybe_placeholders=True,
            propagate_positions=True,
            debug=debug,
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

    def as_graph(self, **kwargs) -> SequencerProgramGraph:
        """
        Create a graphviz digraph of the state notation diagram.

        Returns
        -------
        graph : SequencerProgramGraph
        """
        return SequencerProgramGraph(self, **kwargs)


@lark.visitors.v_args(inline=True)
class _ProgramTransformer(lark.visitors.Transformer):
    def __init__(self, cls, fn, visit_tokens=False):
        super().__init__(
            visit_tokens=visit_tokens,
        )
        self.fn = str(fn)
        self.cls = cls
        self._code_transitions = []

    def program(
        self,
        program_token: lark.Token,
        name: lark.Token,
        program_param: Optional[str],
        initial_defns: Sequence[Definition],
        entry: Block,
        state_sets: Sequence[StateSet],
        exit: Block,
        final_defns: Sequence[Definition],
    ):
        """
        PROGRAM NAME program_param initial_defns entry state_sets exit final_defns
        """
        return self.cls(
            context=context_from_token(self.fn, program_token),
            params=program_param,
            name=str(name),
            initial_definitions=initial_defns,
            entry=entry,
            state_sets=state_sets,
            exit=exit,
            final_definitions=final_defns,
        )

    def program_param(self, *args):
        if not args:
            return None
        """
        LPAREN string RPAREN
        """
        return str(args[1])

    initial_defns = transformer.tuple_args
    final_defns = transformer.tuple_args

    def assign(self, assign_token, variable, _):
        """
        ASSIGN variable SEMICOLON
        """
        return Assignment(
            context=context_from_token(self.fn, assign_token),
            variable=str(variable),
        )

    def assign_string(self, assign_token, variable, to_, value, _):
        """
        ASSIGN variable to string SEMICOLON
        """
        return Assignment(
            context=context_from_token(self.fn, assign_token),
            variable=str(variable),
            value=str(value),
        )

    def assign_subscript_string(self, assign_token, variable, subscript, to_, value, _):
        """
        ASSIGN variable subscript to string SEMICOLON
        """
        return Assignment(
            context=context_from_token(self.fn, assign_token),
            variable=str(variable),
            value=str(value),
            subscript=str(subscript),
        )

    def assign_strings(self, assign_token, variable, to_, _, strings, *__):
        """
        ASSIGN variable to LBRACE strings RBRACE SEMICOLON
        """
        return Assignment(
            context=context_from_token(self.fn, assign_token),
            variable=str(variable),
            value=tuple(str(value) for value in strings),
        )

    strings = transformer.tuple_args

    def monitor(self, monitor_token, variable, opt_subscript, _):
        """
        MONITOR variable opt_subscript SEMICOLON
        """
        return Monitor(
            context=context_from_token(self.fn, monitor_token),
            variable=str(variable),
            subscript=str(opt_subscript) if opt_subscript else None,
        )

    def sync(self, sync_token, variable, subscript, _, event_flag, __):
        """
        SYNC variable opt_subscript to event_flag SEMICOLON
        """
        return Sync(
            context=context_from_token(self.fn, sync_token),
            variable=str(variable),
            subscript=str(subscript) if subscript else None,
            event_flag=event_flag,
            queued=False,
        )

    def syncq_flagged(
        self, syncq_token, variable, subscript, _, event_flag, syncq_size, __
    ):
        """
        SYNCQ variable opt_subscript to event_flag syncq_size SEMICOLON
        """
        return Sync(
            context=context_from_token(self.fn, syncq_token),
            variable=str(variable),
            subscript=str(subscript) if subscript else None,
            event_flag=event_flag,
            queued=True,
            queue_size=syncq_size,
        )

    def syncq(self, syncq_token, variable, subscript, syncq_size, _):
        """
        SYNCQ variable opt_subscript syncq_size SEMICOLON
        """
        return Sync(
            context=context_from_token(self.fn, syncq_token),
            variable=str(variable),
            subscript=str(subscript) if subscript else None,
            queued=True,
            queue_size=syncq_size,
        )

    event_flag = transformer.stringify
    variable = transformer.pass_through

    def syncq_size(self, size=None):
        """
        INTCON?
        """
        return int(size) if size else None

    opt_subscript = transformer.pass_through

    def subscript(self, _, value, __):
        """
        LBRACKET INTCON RBRACKET
        """
        return value

    def declaration(self, basetype: Type, init_declarators, _):
        """
        basetype init_declarators SEMICOLON
        """
        return Declaration(
            context=basetype.context,
            type=basetype,
            declarators=init_declarators,
        )

    def foreign_declaration(self, foreign_token, variables, _):
        """
        FOREIGN variables SEMICOLON
        """
        return ForeignDeclaration(
            context=context_from_token(self.fn, foreign_token),
            names=tuple(str(variable) for variable in variables),
            type=None,
            declarators=None,
        )

    init_declarators = transformer.tuple_args

    def init_declarator(self, declarator: Declarator, *equal_expr):
        if equal_expr:
            _, value = equal_expr
            declarator.value = value
        return declarator

    def declarator(self, variable: lark.Token):
        return Declarator(
            context=context_from_token(self.fn, variable),
            object=Variable(
                context=context_from_token(self.fn, variable),
                name=str(variable),
            ),
        )

    def declarator_decls(self, declarator, _, param_decls, __):
        return Declarator(
            context=declarator.context,
            object=declarator,
            params=param_decls,
        )

    def declarator_subscript(self, declarator, subscript):
        return Declarator(
            context=declarator.context,
            object=declarator,
            subscript=str(subscript),
        )

    def declarator_paren(self, _, declarator, __):
        return Declarator(
            context=declarator.context,
            object=declarator,
            modifier="()",
        )

    def declarator_deref(self, asterisk, declarator):
        return Declarator(
            context=context_from_token(self.fn, asterisk),
            object=declarator,
            modifier="*",
        )

    def declarator_const(self, const, declarator):
        return Declarator(
            context=context_from_token(self.fn, const),
            object=declarator,
            modifier="const",
        )

    param_decls = transformer.tuple_args

    def param_decl(self, type_, declarator=None):
        """
        basetype declarator
        type_expr
        """
        return ParameterDeclarator(
            context=type_.context, type=type_, declarator=declarator
        )

    variables = transformer.tuple_args

    init_expr = transformer.pass_through

    def typed_init_expr(self, lparen, type_expr, _, __, init_exprs, ___):
        """
        type_expr RPAREN LBRACE init_exprs RBRACE
        LBRACE init_exprs RBRACE
        """
        return InitExpression(
            context=context_from_token(self.fn, lparen),
            expressions=init_exprs,
            type=type_expr,
        )

    def untyped_init_expr(self, lbrace, init_exprs, _):
        """
        LBRACE init_exprs RBRACE
        """
        return InitExpression(
            context=context_from_token(self.fn, lbrace),
            expressions=init_exprs,
            type=None,
        )

    init_exprs = transformer.tuple_args

    def basetype(self, *type_info):
        return Type(
            context=context_from_token(self.fn, type_info[0]),
            name=" ".join(type_info),
        )

    def type_expr(self, basetype: Type, abs_decl: Optional[AbstractDeclarator] = None):
        basetype.abstract = abs_decl
        return basetype

    def abs_decl_mod(self, token, abs_decl=None, *_):
        """
        LPAREN abs_decl RPAREN
        ASTERISK abs_decl?
        CONST abs_decl?
        """
        if abs_decl is not None:
            abs_decl.modifier = str(token)
            return abs_decl

        return token

    def abs_decl_subscript(self, abs_decl, subscript):
        # TODO I think these may be wrong
        if abs_decl is None:
            return AbstractDeclarator(
                context=context_from_token(self.fn, subscript),
                subscript=str(subscript),
            )

        abs_decl.subscript = subscript
        return abs_decl

    def abs_decl_params(self, abs_decl, lparen, param_decls, rparen):
        """
        abs_decl? LPAREN param_decls RPAREN
        """
        # TODO I think these may be wrong
        if abs_decl is not None:
            abs_decl.params = param_decls
            return abs_decl

        return AbstractDeclarator(
            context=context_from_token(self.fn, lparen),
            params=param_decls,
        )

    def option(self, option_token, value, name, _):
        """
        OPTION option_value NAME SEMICOLON
        """
        return Option(
            context=context_from_token(self.fn, option_token),
            name=str(name),
            enable=(value == "+"),  # "+" or "-"
        )

    option_value = transformer.stringify
    state_sets = transformer.tuple_args

    def state_set(self, state_set_token, name, _, defns, states, __):
        """
        STATE_SET NAME LBRACE ss_defns states RBRACE
        """
        return StateSet(
            context=context_from_token(self.fn, state_set_token),
            name=str(name),
            definitions=defns,
            states=states,
        )

    ss_defns = transformer.tuple_args

    states = transformer.tuple_args

    def state(
        self,
        state_token,
        name: lark.Token,
        _,
        definitions: Sequence[Definition],
        entry: Block,
        transitions: Sequence[Transition],
        exit: Block,
        __,
    ):
        """
        STATE NAME LBRACE state_defns entry? transitions exit? RBRACE
        """
        code_transitions = list(self._code_transitions)
        self._code_transitions = []
        return State(
            context=context_from_token(self.fn, state_token),
            name=str(name),
            definitions=definitions,
            entry=entry,
            transitions=transitions,
            exit=exit,
            code_transitions=code_transitions,
        )

    state_defns = transformer.tuple_args

    def entry(self, *args):
        if args:
            _, block = args
            return block
        return None

    exit = entry
    transitions = transformer.tuple_args

    def transition(
        self,
        when: lark.Token,
        _,
        condition: OptionalExpression,
        __,
        block: Block,
        ___,
        state: lark.Token,
    ):
        """
        WHEN LPAREN [ condition ] RPAREN block STATE NAME
        """
        return Transition(
            context=context_from_token(self.fn, when),
            condition=condition,
            block=block,
            target_state=str(state),
        )

    def transition_exit(
        self, when: lark.Token, _, condition: Expression, __, block: Block, ___
    ):
        """
        WHEN LPAREN [ condition ] RPAREN block EXIT
        """
        return ExitTransition(
            context=context_from_token(self.fn, when),
            condition=condition,
            block=block,
        )

    condition = transformer.pass_through

    def block(self, lbrace: lark.Token, definitions, statements, _):
        """
        LBRACE block_defns statements RBRACE
        """
        return Block(
            context=context_from_token(self.fn, lbrace),
            definitions=definitions,
            statements=statements,
        )

    block_defns = transformer.tuple_args
    statements = transformer.tuple_args
    statement = transformer.pass_through

    def break_statement(self, break_token: lark.Token, _):
        return BreakStatement(
            context=context_from_token(self.fn, break_token),
        )

    def continue_statement(self, continue_token: lark.Token, _):
        return ContinueStatement(
            context=context_from_token(self.fn, continue_token),
        )

    def return_statement(self, return_token: lark.Token, value: Expression, _):
        return ReturnStatement(
            context=context_from_token(self.fn, return_token),
            value=value,
        )

    def state_statement(self, state_token: lark.Token, name: lark.Token, _):
        statement = StateStatement(
            context=context_from_token(self.fn, state_token),
            name=str(name),
        )
        self._code_transitions.append(statement)
        return statement

    def while_statement(
        self,
        while_token: lark.Token,
        _,
        condition: OptionalExpression,
        __,
        statement: Statement,
    ):
        return WhileStatement(
            context=context_from_token(self.fn, while_token),
            condition=condition,
            body=statement,
        )

    def expr_statement(self, expression: CommaSeparatedExpressions, semicolon: lark.Token):
        return ExpressionStatement(
            context=context_from_token(self.fn, semicolon),
            expression=expression,
        )

    statement = transformer.pass_through

    def if_statement(
        self,
        if_token: lark.Token,
        _,
        condition: OptionalExpression,
        __,
        body: Expression,
        *else_clause
    ):
        if else_clause:
            else_token, else_body = else_clause
        else:
            else_body = None

        """
        IF LPAREN comma_expr RPAREN statement (ELSE statement)?
        """
        return IfStatement(
            context=context_from_token(self.fn, if_token),
            condition=condition,
            body=body,
            else_body=else_body,
        )

    def for_statement(
        self,
        for_token: lark.Token,
        _,
        init: OptionalExpression,
        __,
        condition: OptionalExpression,
        ___,
        increment: OptionalExpression,
        ____,
        statement: Statement,
    ):
        """
        FOR LPAREN [ comma_expr ] SEMICOLON [ comma_expr ] SEMICOLON [ comma_expr ] RPAREN statement
        """
        return ForStatement(
            context=context_from_token(self.fn, for_token),
            init=init,
            condition=condition,
            increment=increment,
            statement=statement,
        )

    def unary_prefix_expr(self, operator: lark.Token, expr: Expression):
        return UnaryPrefixExpression(
            context=context_from_token(self.fn, operator),
            operator=str(operator),
            expression=expr,
        )

    def unary_postfix_expr(self, expr: Expression, operator: lark.Token):
        return UnaryPostfixExpression(
            context=context_from_token(self.fn, operator),
            expression=expr,
            operator=str(operator),
        )

    def binary_operator_expr(
        self, lhand: Expression, operator: lark.Token, rhand: Expression
    ):
        return BinaryOperatorExpression(
            context=context_from_token(self.fn, operator),
            left=lhand,
            operator=str(operator),
            right=rhand,
        )

    def type_cast_expr(self, lparen, type_expr, _, expr):
        return TypeCastExpression(
            context=context_from_token(self.fn, lparen),
            type=type_expr,
            expression=expr,
        )

    def sizeof(self, sizeof_token: lark.Token, _, type_expr: Type, __):
        return SizeofExpression(
            context=context_from_token(self.fn, sizeof_token),
            type=type_expr,
        )

    def exit_expr(self, exit_token: lark.Token, _, args: OptionalExpression, __):
        return ExitExpression(
            context=context_from_token(self.fn, exit_token),
            args=args,
        )

    def expr_with_args(
        self,
        expression: Expression,
        tok: lark.Token,
        arguments: OptionalExpression,
        _,
    ):
        return ExpressionWithArguments(
            context=context_from_token(self.fn, tok),
            expression=expression,
            arguments=arguments,
        )

    def bracket_expr(self, outer: Expression, tok: lark.Token, inner: Expression, __):
        return BracketedExpression(
            context=context_from_token(self.fn, tok),
            outer=outer,
            inner=inner,
        )

    def parenthesized_expr(self, lparen: lark.Token, expression: Expression, _):
        return ParenthesisExpression(
            context=context_from_token(self.fn, lparen),
            expression=expression,
        )

    def ternary_expr(self, condition, question, if_true, _, if_false):
        return TernaryExpression(
            context=context_from_token(self.fn, question),
            condition=condition,
            if_true=if_true,
            if_false=if_false,
        )

    def member_expr(self, expr: Expression, operator: lark.Token, member: lark.Token):
        return MemberExpression(
            context=context_from_token(self.fn, operator),
            parent=expr,
            member=str(member),
            dereference=operator == "->",
        )

    def variable_literal(self, name):
        return Variable(
            context=context_from_token(self.fn, name),
            name=str(name),
        )

    def comma_expr(self, *expressions: Expression) -> CommaSeparatedExpressions:
        return CommaSeparatedExpressions(
            context=expressions[0].context,
            expressions=list(expressions),
        )

    @lark.visitors.v_args(tree=True)
    def literal_expr(self, item):
        child = item.children[0]
        if isinstance(child, lark.Token):
            context = context_from_token(self.fn, child)
            value = str(child)
        else:
            context = context_from_token(self.fn, child.children[0])
            value = "".join(child.children)
        return Literal(
            context=context,
            type=item.data,
            # [Tree('variable', [Token('NAME', 'seq_test_init')])]
            value=value,
        )

    args = transformer.tuple_args

    string = transformer.pass_through
    member = transformer.pass_through

    def funcdef(self, basetype: Type, declarator: Declarator, block: Block):
        """
        basetype declarator block
        """
        return FuncDef(
            context=basetype.context,
            type=basetype,
            declarator=declarator,
            block=block,
        )

    def structdef(self, struct_token, name, members, _):
        """
        STRUCT NAME members SEMICOLON
        """
        return StructDef(
            context=context_from_token(self.fn, struct_token),
            name=str(name),
            members=members,
        )

    def members(self, _, decls, __):
        """
        LBRACE member_decls RBRACE
        """
        return decls

    member_decls = transformer.tuple_args

    def member_decl(self, type: Type, declarator: Declarator, _):
        """
        basetype declarator SEMICOLON
        """
        return StructMemberDecl(
            context=type.context,
            type=type,
            declarator=declarator,
        )

    member_decl_ccode = transformer.pass_through

    def c_code(self, c_code):
        return CCode(
            context=context_from_token(self.fn, c_code),
            code=str(c_code),
        )
