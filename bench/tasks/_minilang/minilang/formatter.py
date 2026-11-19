"""Prints a syntax tree back as source, in one standard layout: 4-space indents, one statement per line, and only the
parentheses the meaning needs. format_source(format_source(x)) == format_source(x)."""
from . import ast
from .lexer import tokenize
from .parser import PRECEDENCE, RIGHT, UNARY, parse
from .values import quote

ATOM = 100  # literals, names, calls and indexes: never need parentheses
INDENT = "    "


def format_source(source):
    return format_program(parse(tokenize(source)))


def format_program(program):
    return "".join(statement(stmt, 0) for stmt in program.stmts)


def statement(node, depth):
    pad = INDENT * depth
    if isinstance(node, ast.Let):
        return f"{pad}let {node.name} = {expr(node.value, depth)};\n"
    if isinstance(node, ast.Assign):
        return f"{pad}{expr(node.target, depth)} = {expr(node.value, depth)};\n"
    if isinstance(node, ast.ExprStmt):
        return f"{pad}{expr(node.expr, depth)};\n"
    if isinstance(node, ast.Return):
        return f"{pad}return;\n" if node.value is None else f"{pad}return {expr(node.value, depth)};\n"
    if isinstance(node, ast.FnDecl):
        return f"{pad}fn {node.name}({', '.join(node.params)}) {block(node.body, depth)}\n"
    if isinstance(node, ast.While):
        return f"{pad}while {expr(node.cond, depth)} {block(node.body, depth)}\n"
    if isinstance(node, ast.If):
        return pad + if_chain(node, depth) + "\n"
    raise TypeError(f"not a statement: {node!r}")


def if_chain(node, depth):  # if ... {} else if ... {} else {}, without the indent and newline
    text = f"if {expr(node.cond, depth)} {block(node.then, depth)}"
    rest = node.else_
    if rest is None:
        return text
    if len(rest.stmts) == 1 and isinstance(rest.stmts[0], ast.If):
        return text + " else " + if_chain(rest.stmts[0], depth)
    return text + " else " + block(rest, depth)


def block(node, depth):
    if not node.stmts:
        return "{}"
    return "{\n" + "".join(statement(stmt, depth + 1) for stmt in node.stmts) + INDENT * depth + "}"


def expr(node, depth, need=0):  # need: the precedence below which node must be in parentheses
    text, prec = _expr(node, depth)
    return f"({text})" if prec < need else text


def _expr(node, depth):  # -> (text, precedence)
    if isinstance(node, ast.Num):
        return repr(node.value), ATOM
    if isinstance(node, ast.Str):
        return quote(node.value), ATOM
    if isinstance(node, ast.Bool):
        return ("true" if node.value else "false"), ATOM
    if isinstance(node, ast.Nil):
        return "nil", ATOM
    if isinstance(node, ast.Name):
        return node.name, ATOM
    if isinstance(node, ast.ListLit):
        return "[" + ", ".join(expr(item, depth) for item in node.items) + "]", ATOM
    if isinstance(node, ast.Index):
        return f"{expr(node.target, depth, ATOM)}[{expr(node.index, depth)}]", ATOM
    if isinstance(node, ast.Call):
        return f"{expr(node.callee, depth, ATOM)}({', '.join(expr(a, depth) for a in node.args)})", ATOM
    if isinstance(node, ast.FnLit):
        return f"fn({', '.join(node.params)}) {block(node.body, depth)}", ATOM
    if isinstance(node, ast.Unary):
        space = " " if node.op == "not" else ""
        return f"{node.op}{space}{expr(node.operand, depth, UNARY)}", UNARY
    if isinstance(node, ast.Binary):
        prec = PRECEDENCE[node.op]
        right_assoc = node.op in RIGHT
        left = expr(node.left, depth, prec + 1 if right_assoc else prec)
        right = expr(node.right, depth, prec if right_assoc else prec + 1)
        return f"{left} {node.op} {right}", prec
    raise TypeError(f"not an expression: {node!r}")
