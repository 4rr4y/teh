import unittest

from minilang.errors import EvalError
from tests.helpers import output, value


class TestBuiltins(unittest.TestCase):
    def test_print(self):
        self.assertEqual(output('print("a", 1, 2.5, nil, true, ["x", [1]]);'), ['a 1 2.5 nil true ["x", [1]]'])
        self.assertEqual(output("print();"), [""])

    def test_conversions(self):
        self.assertEqual(value('str(1.0) + "!"'), "1.0!")
        self.assertEqual(value('num(" 42 ") + 1'), "43")
        self.assertEqual(value('num("2.5")'), "2.5")
        self.assertEqual(value('[type(nil), type(1), type("s"), type([]), type(print)]'),
                         '["nil", "number", "string", "list", "function"]')
        with self.assertRaises(EvalError):
            output('num("ten");')

    def test_range(self):
        self.assertEqual(value("range(3)"), "[0, 1, 2]")
        self.assertEqual(value("range(0)"), "[]")
        self.assertEqual(value("range(10, 0, -3)"), "[10, 7, 4, 1]")

    def test_lists(self):
        self.assertEqual(output("let xs = [1]; push(xs, 2); print(pop(xs), xs, len(xs));"), ["2 [1] 1"])
        self.assertEqual(value('join(["a", 1], "-")'), "a-1")
        self.assertEqual(value('split("a,b,,c", ",")'), '["a", "b", "", "c"]')

    def test_numbers(self):
        self.assertEqual(value("[abs(-3), min(4, 2, 8), max([1, 9, 3])]"), "[3, 2, 9]")

    def test_errors(self):
        for src in ("len(5);", "pop([]);", "range(1.5);", "min();", 'split("a", "");', "print(len());"):
            with self.assertRaises(EvalError, msg=src):
                output(src)
