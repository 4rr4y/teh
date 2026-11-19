"""The syntax tree. Expressions and statements are plain dataclasses."""
from dataclasses import dataclass, field


# ----- Expressions -----
@dataclass
class Num:
    value: object  # int or float


@dataclass
class Str:
    value: str


@dataclass
class Bool:
    value: bool


@dataclass
class Nil:
    pass


@dataclass
class Name:
    name: str
    line: int = 0


@dataclass
class ListLit:
    items: list


@dataclass
class Index:
    target: object
    index: object
    line: int = 0


@dataclass
class Unary:
    op: str  # "-" or "not"
    operand: object


@dataclass
class Binary:
    op: str  # arithmetic, comparison, "and", "or"
    left: object
    right: object
    line: int = 0


@dataclass
class Call:
    callee: object
    args: list
    line: int = 0


@dataclass
class FnLit:  # fn(a, b) { ... } as an expression
    params: list
    body: object


# ----- Statements -----
@dataclass
class Block:
    stmts: list = field(default_factory=list)


@dataclass
class Let:
    name: str
    value: object


@dataclass
class Assign:
    target: object  # Name or Index
    value: object


@dataclass
class ExprStmt:
    expr: object


@dataclass
class FnDecl:
    name: str
    params: list
    body: Block


@dataclass
class If:
    cond: object
    then: Block
    else_: object = None  # a Block, or None; "else if" is a Block holding one If


@dataclass
class While:
    cond: object
    body: Block


@dataclass
class Return:
    value: object = None


@dataclass
class Program:
    stmts: list
