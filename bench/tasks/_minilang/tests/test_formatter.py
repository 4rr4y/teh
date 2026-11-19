import unittest

from minilang.formatter import format_source


class TestFormatter(unittest.TestCase):
    def test_layout(self):
        self.assertEqual(format_source("fn f(a,b){let c=a+b;if c>2{return c;}else{return;}}"),
                         "fn f(a, b) {\n    let c = a + b;\n    if c > 2 {\n        return c;\n    } else {\n"
                         "        return;\n    }\n}\n")

    def test_else_if(self):
        self.assertEqual(format_source("if a { x; } else if b { y; } else { }"),
                         "if a {\n    x;\n} else if b {\n    y;\n} else {}\n")

    def test_needed_parentheses_kept(self):
        self.assertEqual(format_source("x = (a + b) * c;"), "x = (a + b) * c;\n")
        self.assertEqual(format_source("x = (-2) ^ 2;"), "x = (-2) ^ 2;\n")
        self.assertEqual(format_source("x = a - (b - c);"), "x = a - (b - c);\n")

    def test_needless_parentheses_dropped(self):
        self.assertEqual(format_source("x = a + (b * c);"), "x = a + b * c;\n")
        self.assertEqual(format_source("x = (a - b) - c;"), "x = a - b - c;\n")

    def test_literals(self):
        self.assertEqual(format_source(r'print("q\"\n", 2.50, [nil, true]);'), 'print("q\\"\\n", 2.5, [nil, true]);\n')

    def test_function_expression(self):
        self.assertEqual(format_source("let f = fn(x) { return x; };"), "let f = fn(x) {\n    return x;\n};\n")

    def test_idempotent(self):
        src = "while not done and n < 10 { n = n + 1; xs[n % 2] = -n ^ 2; }"
        once = format_source(src)
        self.assertEqual(format_source(once), once)
