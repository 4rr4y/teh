import unittest

from minilang import ast
from minilang.errors import ParseError
from minilang.lexer import tokenize
from minilang.parser import parse


def expression(src):
    return parse(tokenize(src + ";")).stmts[0].expr


def shape(node):  # a compact form of an expression tree: (op, left, right)
    if isinstance(node, ast.Binary):
        return (node.op, shape(node.left), shape(node.right))
    if isinstance(node, ast.Unary):
        return (node.op, shape(node.operand))
    if isinstance(node, ast.Num):
        return node.value
    if isinstance(node, ast.Name):
        return node.name
    return type(node).__name__


class TestParser(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(shape(expression("1 + 2 * 3")), ("+", 1, ("*", 2, 3)))
        self.assertEqual(shape(expression("(1 + 2) * 3")), ("*", ("+", 1, 2), 3))
        self.assertEqual(shape(expression("a or b and c == d")), ("or", "a", ("and", "b", ("==", "c", "d"))))

    def test_left_associative(self):
        self.assertEqual(shape(expression("10 - 4 - 3")), ("-", ("-", 10, 4), 3))

    def test_power(self):
        self.assertEqual(shape(expression("2 ^ 3 ^ 2")), ("^", 2, ("^", 3, 2)))
        self.assertEqual(shape(expression("-2 ^ 2")), ("-", ("^", 2, 2)))

    def test_unary(self):
        self.assertEqual(shape(expression("-a * b")), ("*", ("-", "a"), "b"))
        self.assertEqual(shape(expression("not a and b")), ("and", ("not", "a"), "b"))

    def test_calls_and_indexes(self):
        node = expression("f(1, 2)[0](x)")
        self.assertIsInstance(node, ast.Call)
        self.assertIsInstance(node.callee, ast.Index)
        self.assertEqual(len(node.callee.target.args), 2)

    def test_statements(self):
        program = parse(tokenize("let x = 1; x = 2; xs[0] = 3; fn f(a) { return; } if x { } else if y { } else { }"))
        self.assertEqual([type(s).__name__ for s in program.stmts], ["Let", "Assign", "Assign", "FnDecl", "If"])
        else_if = program.stmts[4].else_.stmts[0]
        self.assertIsInstance(else_if, ast.If)
        self.assertEqual(else_if.else_.stmts, [])

    def test_trailing_comma(self):
        self.assertEqual(len(expression("[1, 2, 3,]").items), 3)

    def test_errors(self):
        for src in ("let = 3;", "1 + ;", "f(1, 2;", "if x { y;", "1 = 2;", "fn f(a, a) {}", "x"):
            with self.assertRaises(ParseError, msg=src):
                parse(tokenize(src))

    def test_error_line(self):
        with self.assertRaises(ParseError) as e:
            parse(tokenize("let a = 1;\nlet b = ;\n"))
        self.assertEqual(e.exception.line, 2)
