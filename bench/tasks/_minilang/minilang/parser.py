"""Turns tokens into a syntax tree: statements by recursive descent, expressions by precedence climbing."""
from .ast import (Assign, Binary, Block, Bool, Call, ExprStmt, FnDecl, FnLit, If, Index, Let, ListLit, Name, Nil,
                  Num, Program, Return, Str, Unary, While)
from .errors import ParseError

# Binary operators, loosest first. ^ is right-associative: 2 ^ 3 ^ 2 is 2 ^ (3 ^ 2)
PRECEDENCE = {"or": 1, "and": 2, "==": 3, "!=": 3, "<": 4, "<=": 4, ">": 4, ">=": 4,
              "+": 5, "-": 5, "*": 6, "/": 6, "%": 6, "^": 8}
RIGHT = {"^"}
UNARY = 7  # - and not bind tighter than * but looser than ^: -2 ^ 2 is -(2 ^ 2)


def parse(tokens):
    return Parser(tokens).program()


class Parser:
    def __init__(self, tokens):
        self.tokens, self.pos = tokens, 0

    # ----- Tokens -----
    def peek(self, ahead=0):
        return self.tokens[min(self.pos + ahead, len(self.tokens) - 1)]

    def next(self):
        token = self.peek()
        self.pos += 1
        return token

    def at(self, kind, value=None):
        token = self.peek()
        return token.kind == kind and (value is None or token.value == value)

    def expect(self, kind, value=None):
        if not self.at(kind, value):
            raise ParseError(f"expected {value or kind}, found {describe(self.peek())}", self.peek().line)
        return self.next()

    # ----- Statements -----
    def program(self):
        stmts = []
        while not self.at("eof"):
            stmts.append(self.statement())
        return Program(stmts)

    def block(self):
        self.expect("op", "{")
        stmts = []
        while not self.at("op", "}"):
            if self.at("eof"):
                raise ParseError("unclosed block: expected }", self.peek().line)
            stmts.append(self.statement())
        self.expect("op", "}")
        return Block(stmts)

    def statement(self):
        if self.at("kw", "let"):
            self.next()
            name = self.expect("name").value
            self.expect("op", "=")
            value = self.expression()
            self.expect("op", ";")
            return Let(name, value)
        if self.at("kw", "fn") and self.peek(1).kind == "name":
            self.next()
            name = self.next().value
            params, body = self.function_rest()
            return FnDecl(name, params, body)
        if self.at("kw", "if"):
            return self.if_statement()
        if self.at("kw", "while"):
            self.next()
            cond = self.expression()
            return While(cond, self.block())
        if self.at("kw", "return"):
            self.next()
            value = None if self.at("op", ";") else self.expression()
            self.expect("op", ";")
            return Return(value)
        line = self.peek().line
        expr = self.expression()
        if self.at("op", "="):
            if not isinstance(expr, (Name, Index)):
                raise ParseError("can only assign to a name or an index", line)
            self.next()
            value = self.expression()
            self.expect("op", ";")
            return Assign(expr, value)
        self.expect("op", ";")
        return ExprStmt(expr)

    def if_statement(self):
        self.expect("kw", "if")
        cond = self.expression()
        then, else_ = self.block(), None
        if self.at("kw", "else"):
            self.next()
            else_ = Block([self.if_statement()]) if self.at("kw", "if") else self.block()
        return If(cond, then, else_)

    def function_rest(self):  # (params) { body }, after "fn" and the name if any
        self.expect("op", "(")
        params = []
        while not self.at("op", ")"):
            name = self.expect("name").value
            if name in params:
                raise ParseError(f"parameter {name!r} appears twice", self.peek().line)
            params.append(name)
            if not self.at("op", ")"):
                self.expect("op", ",")
        self.expect("op", ")")
        return params, self.block()

    # ----- Expressions -----
    def expression(self, min_prec=1):
        left = self.prefix()
        while True:
            token = self.peek()
            op = token.value if token.kind in ("op", "kw") else None
            prec = PRECEDENCE.get(op)
            if prec is None or prec < min_prec:
                return left
            self.next()
            right = self.expression(prec if op in RIGHT else prec + 1)
            left = Binary(op, left, right, token.line)

    def prefix(self):
        token = self.next()
        kind, value = token.kind, token.value
        if kind == "num":
            node = Num(value)
        elif kind == "str":
            node = Str(value)
        elif kind == "name":
            node = Name(value, token.line)
        elif kind == "kw" and value in ("true", "false"):
            node = Bool(value == "true")
        elif kind == "kw" and value == "nil":
            node = Nil()
        elif kind == "kw" and value == "fn":
            node = FnLit(*self.function_rest())
        elif (kind, value) in (("op", "-"), ("kw", "not")):
            return Unary(value, self.expression(UNARY))
        elif (kind, value) == ("op", "("):
            node = self.expression()
            self.expect("op", ")")
        elif (kind, value) == ("op", "["):
            node = ListLit(self.items("]"))
        else:
            raise ParseError(f"unexpected {describe(token)}", token.line)
        return self.postfix(node)

    def postfix(self, node):  # calls and indexes: f(x)[0](y)
        while True:
            line = self.peek().line
            if self.at("op", "("):
                self.next()
                node = Call(node, self.items(")"), line)
            elif self.at("op", "["):
                self.next()
                index = self.expression()
                self.expect("op", "]")
                node = Index(node, index, line)
            else:
                return node

    def items(self, close):  # comma-separated expressions up to close; a trailing comma is allowed
        out = []
        while not self.at("op", close):
            out.append(self.expression())
            if not self.at("op", close):
                self.expect("op", ",")
        self.expect("op", close)
        return out


def describe(token):
    if token.kind == "eof":
        return "end of input"
    return repr(token.value) if token.kind == "str" else f"'{token.value}'"
