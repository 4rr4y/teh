import unittest

from minilang.errors import EvalError
from tests.helpers import output, value


class TestArithmetic(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(value("1 + 2 * 3"), "7")
        self.assertEqual(value("7 / 2"), "3.5")
        self.assertEqual(value("6 / 3"), "2")
        self.assertEqual(value("-7 % 3"), "2")
        self.assertEqual(value("2 ^ 10"), "1024")

    def test_power_and_minus(self):
        self.assertEqual(value("-2 ^ 2"), "-4")
        self.assertEqual(value("(-2) ^ 2"), "4")

    def test_strings_and_lists(self):
        self.assertEqual(value('"ab" + "cd"'), "abcd")
        self.assertEqual(value('"ab" * 3'), "ababab")
        self.assertEqual(value("[1] + [2, 3]"), "[1, 2, 3]")

    def test_errors(self):
        for src in ("print(1 / 0);", 'print(1 + "a");', "print(-\"a\");", 'print(1 < "a");'):
            with self.assertRaises(EvalError, msg=src):
                output(src)


class TestLogic(unittest.TestCase):
    def test_truthiness(self):
        self.assertEqual(value('0 and "yes"'), "yes")
        self.assertEqual(value('"" or "no"'), "")
        self.assertEqual(value("nil or false"), "false")
        self.assertEqual(value("not []"), "false")

    def test_short_circuit(self):
        self.assertEqual(output("let n = 0; fn bump() { n = n + 1; return true; } "
                                "let a = false and bump(); let b = true or bump(); print(n);"), ["0"])

    def test_equality(self):
        self.assertEqual(value("1 == 1.0"), "true")
        self.assertEqual(value('1 == "1"'), "false")
        self.assertEqual(value("[1, [2]] == [1, [2]]"), "true")
        self.assertEqual(value("nil == false"), "false")


class TestScopes(unittest.TestCase):
    def test_blocks_hide_and_assign(self):
        self.assertEqual(output("let x = 1; if true { let x = 2; print(x); } print(x); "
                                "if true { x = 3; } print(x);"), ["2", "1", "3"])

    def test_undeclared(self):
        with self.assertRaises(EvalError):
            output("y = 1;")
        with self.assertRaises(EvalError):
            output("let x = 1; let x = 2;")

    def test_closures(self):
        self.assertEqual(output("""
            fn counter() {
                let n = 0;
                fn next() { n = n + 1; return n; }
                return next;
            }
            let a = counter();
            let b = counter();
            a(); a();
            print(a(), b());
        """), ["3 1"])

    def test_function_expressions(self):
        self.assertEqual(output("let twice = fn(f, x) { return f(f(x)); }; print(twice(fn(x) { return x * 3; }, 2));"),
                         ["18"])

    def test_recursion(self):
        self.assertEqual(output("fn fact(n) { if n <= 1 { return 1; } return n * fact(n - 1); } print(fact(20));"),
                         ["2432902008176640000"])
        with self.assertRaises(EvalError):
            output("fn loop(n) { return loop(n + 1); } loop(0);")

    def test_return_nil(self):
        self.assertEqual(output("fn f() { return; } fn g() { } print(f(), g());"), ["nil nil"])

    def test_wrong_arguments(self):
        with self.assertRaises(EvalError):
            output("fn f(a) { } f(1, 2);")


class TestLists(unittest.TestCase):
    def test_indexing(self):
        self.assertEqual(output('let xs = [1, 2, 3]; xs[0] = 9; print(xs, xs[-1], "abc"[1]);'), ["[9, 2, 3] 3 b"])

    def test_shared(self):
        self.assertEqual(output("let a = [1]; let b = a; push(b, 2); print(a);"), ["[1, 2]"])

    def test_bad_indexes(self):
        for src in ("[1][1];", "[1][true];", "5[0];", '"abc"[0] = "x";'):
            with self.assertRaises(EvalError, msg=src):
                output(src)

    def test_loop_over_range(self):
        self.assertEqual(output("let xs = range(1, 4); let total = 0; let i = 0; "
                                "while i < len(xs) { total = total + xs[i]; i = i + 1; } print(total);"), ["6"])
