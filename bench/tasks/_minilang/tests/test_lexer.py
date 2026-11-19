import unittest

from minilang.errors import LexError
from minilang.lexer import tokenize


def kinds(src):
    return [(t.kind, t.value) for t in tokenize(src)][:-1]


class TestLexer(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(kinds("12 3.25 0"), [("num", 12), ("num", 3.25), ("num", 0)])

    def test_number_then_dot(self):  # "3." isn't a number with a fraction
        with self.assertRaises(LexError):
            tokenize("3.x")

    def test_names_and_keywords(self):
        self.assertEqual(kinds("let x_1 = nil;"),
                         [("kw", "let"), ("name", "x_1"), ("op", "="), ("kw", "nil"), ("op", ";")])

    def test_two_character_symbols(self):
        self.assertEqual([v for _, v in kinds("a<=b==c!=d>=e")], ["a", "<=", "b", "==", "c", "!=", "d", ">=", "e"])

    def test_strings(self):
        self.assertEqual(kinds('"hi there"'), [("str", "hi there")])
        self.assertEqual(kinds(r'"tab\there\nnewline"'), [("str", "tab\there\nnewline")])

    def test_string_escapes(self):
        self.assertEqual(kinds(r'"say \"hi\"" "back\\slash"'), [("str", 'say "hi"'), ("str", "back\\slash")])

    def test_bad_strings(self):
        for src in ('"open', '"two\nlines"', r'"bad \q escape"'):
            with self.assertRaises(LexError, msg=src):
                tokenize(src)

    def test_comments_and_lines(self):
        tokens = tokenize("# a comment\nx # another\n\ny")
        self.assertEqual([(t.value, t.line) for t in tokens[:-1]], [("x", 2), ("y", 4)])

    def test_unexpected(self):
        with self.assertRaises(LexError) as e:
            tokenize("x = 1 @ 2")
        self.assertIn("'@'", str(e.exception))
