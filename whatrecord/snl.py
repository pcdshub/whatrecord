from __future__ import annotations

import collections
import pathlib
import shlex
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union

import lark

from . import transformer
from .common import AnyPath, FullLoadContext
from .transformer import context_from_token


@dataclass
class Definition:
    context: FullLoadContext


@dataclass
class Expression:
    context: FullLoadContext


OptionalExpression = Optional[Union[Expression, Sequence[Expression]]]


@dataclass
class Assignment(Definition):
    variable: str
    value: Optional[Union[str, Sequence[str]]] = None
    subscript: Optional[int] = None


@dataclass
class AbstractDeclarator:
    context: FullLoadContext
    params: Sequence[ParameterDeclarator] = field(default_factory=list)
    modifier: Optional[str] = None
    subscript: Optional[int] = None


@dataclass
class Type:
    context: FullLoadContext
    name: str
    abstract: Optional[AbstractDeclarator] = None


@dataclass
class Monitor(Definition):
    variable: str
    subscript: Optional[int]


@dataclass
class Option(Definition):
    name: str
    enable: bool


@dataclass
class Sync(Definition):
    variable: str
    subscript: Optional[int]
    queued: bool
    event_flag: Optional[str] = None
    queue_size: Optional[int] = None


@dataclass
class Declaration(Definition):
    type: Optional[Type] = None
    declarators: Optional[Sequence[Declarator]] = field(default_factory=list)


@dataclass
class ForeignDeclaration(Declaration):
    names: Sequence[str] = field(default_factory=list)


@dataclass
class Declarator:
    context: FullLoadContext
    object: Union[Declarator, Variable]
    params: OptionalExpression = None
    value: Optional[Expression] = None
    modifier: Optional[str] = None
    subscript: Optional[int] = None


@dataclass
class Parameter:
    context: FullLoadContext


@dataclass
class ParameterDeclarator:
    context: FullLoadContext
    type: Type
    declarator: Optional[Declarator] = None


@dataclass
class State:
    context: FullLoadContext
    name: str
    definitions: Sequence[Definition] = field(default_factory=list)
    transitions: Sequence[Transition] = field(default_factory=list)
    entry: Optional[Block] = None
    exit: Optional[Block] = None


@dataclass
class StateSet:
    context: FullLoadContext
    name: str
    definitions: Sequence[Definition] = field(default_factory=list)
    states: Sequence[State] = field(default_factory=list)


@dataclass
class Transition:
    context: FullLoadContext
    block: Block
    target_state: Optional[str] = None
    condition: OptionalExpression = None


@dataclass
class ExitTransition(Transition):
    ...


@dataclass
class Block:
    context: FullLoadContext
    definitions: Sequence[Definition] = field(default_factory=list)
    statements: Sequence[Statement] = field(default_factory=list)


@dataclass
class Statement:
    context: FullLoadContext


@dataclass
class BreakStatement(Statement):
    ...


@dataclass
class ContinueStatement(Statement):
    ...


@dataclass
class ReturnStatement(Statement):
    value: Optional[Expression] = None


@dataclass
class StateStatement(Statement):
    name: str


@dataclass
class WhileStatement(Statement):
    condition: OptionalExpression
    body: Statement


@dataclass
class ForStatement(Statement):
    init: OptionalExpression
    condition: OptionalExpression
    increment: OptionalExpression
    statement: Statement


@dataclass
class ExpressionStatement(Statement):
    expression: Expression


@dataclass
class IfStatement(Statement):
    condition: Expression
    body: Statement
    else_body: Optional[Statement] = None


@dataclass
class FuncDef(Definition):
    type: Type
    declarator: Declarator
    block: Block


@dataclass
class StructMember:
    context: FullLoadContext
    type: Type
    declarator: Declarator


@dataclass
class CCode(Definition):
    code: str


@dataclass
class StructDef(Definition):
    name: str
    members: Sequence[Union[StructMember, CCode]] = field(default_factory=list)


@dataclass
class Variable(Expression):
    name: str


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


@dataclass
class Literal(Expression):
    type: str
    value: str


@dataclass
class UnaryPrefixExpression(Expression):
    operator: str
    expression: Expression


@dataclass
class UnaryPostfixExpression(Expression):
    expression: Expression
    operator: str


@dataclass
class BinaryOperatorExpression(Expression):
    left: Expression
    operator: str
    right: Expression


@dataclass
class TypeCastExpression(Expression):
    type: Type
    expression: Expression


@dataclass
class TernaryExpression(Expression):
    condition: Expression
    if_true: Expression
    if_false: Expression


@dataclass
class MemberExpression(Expression):
    parent: Expression
    member: str
    dereference: bool  # True = ->, False = .


@dataclass
class SizeofExpression(Expression):
    type: Type


@dataclass
class ExitExpression(Expression):
    expression: Expression


@dataclass
class BracketedExpression(Expression):
    outer: Expression
    inner: Expression


@dataclass
class ParenthesisExpression(Expression):
    expression: Expression


@dataclass
class ExpressionWithArguments(Expression):
    expression: Expression
    arguments: OptionalExpression = None


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


@lark.visitors.v_args(inline=True)
class _ProgramTransformer(lark.visitors.Transformer):
    def __init__(self, cls, fn, visit_tokens=False):
        super().__init__(
            visit_tokens=visit_tokens,
        )
        self.fn = str(fn)
        self.cls = cls

    # def __default__(self, data, children, meta):
    #     raise RuntimeError(f"Unhandled {data}")

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

    def type_expr(self, basetype, abs_decl=None):
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

    def abs_decl_subscript(self, *args):
        # TODO I think these may be wrong
        if len(args) == 1:
            (subscript,) = args
            return AbstractDeclarator(
                context=context_from_token(self.fn, subscript),
                subscript=str(subscript),
            )

        decl, subscript = args
        decl.subscript = subscript
        return decl

    def abs_decl_params(self, *args):
        """
        abs_decl? LPAREN param_decls RPAREN
        """
        # TODO I think these may be wrong
        if len(args) == 4:
            abs_decl, lparen, param_decls, _ = args
            abs_decl.params = param_decls
            return abs_decl

        lparen, param_decls, _ = args
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
        return State(
            context=context_from_token(self.fn, state_token),
            name=str(name),
            definitions=definitions,
            entry=entry,
            transitions=transitions,
            exit=exit,
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
        return StateStatement(
            context=context_from_token(self.fn, state_token),
            name=str(name),
        )

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

    def expr_statement(self, expression: Expression, semicolon: lark.Token):
        return ExpressionStatement(
            context=context_from_token(self.fn, semicolon),
            expression=expression,
        )

    statement = transformer.pass_through

    def if_statement(
        self,
        if_token: lark.Token,
        _,
        condition: Expression,
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

    def exit_expr(self, exit_token: lark.Token, _, expr: Expression, __):
        return ExitExpression(
            context=context_from_token(self.fn, exit_token),
            expression=expr,
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

    comma_expr = transformer.tuple_args

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
        return StructMember(
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
