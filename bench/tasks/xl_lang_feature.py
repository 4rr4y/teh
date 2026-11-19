import shutil, sys, tempfile
from pathlib import Path
from _lib import write, run

PROMPT = ("Implement FEATURE.md in minilang, our small scripting language (see LANGUAGE.md for the language as it "
          "is). Keep the existing tests passing, and add tests for the new feature.")
KIND, SIZE, WEB = "dev", "xl", False
SOURCE = Path(__file__).parent / "_minilang"

FEATURE = """# Feature: for loops, break and continue

## for

    for NAME in EXPRESSION {
        ...
    }

runs the block once for each item of a list, or each character of a string, in order.

- NAME is a new variable each time round, in a scope of its own around the block: functions created in the block
  see that round's value, not the last one. It isn't visible after the loop. The block may assign to it (that
  changes only this round's variable, not the list) but may not declare it again with `let` in the same block
  (the usual error for declaring a name twice applies, as if NAME were declared at the top of the block).
- The loop goes by position: it visits positions 0, 1, 2 ... for as long as the position is less than the list's
  length at that moment. So items pushed onto the list during the loop are visited too, and if items are popped,
  the loop ends sooner.
- Looping over anything other than a list or a string is an EvalError: `can't loop over a number` (or nil, bool,
  function: the value's type as type() names it).
- The expression is evaluated once, before the first round.

## break and continue

- `break;` leaves the innermost enclosing `while` or `for` loop at once. `continue;` skips the rest of the current
  round: a `for` moves on to the next position; a `while` checks its condition again.
- `break` or `continue` outside a loop is a ParseError, with the line: `break outside a loop`, `continue outside a
  loop`. A function body is never inside a loop, even when the function is declared inside one: `while true {
  fn f() { break; } }` is a ParseError.
- `return` inside a loop returns from the function, as before.

## Syntax and tools

- `for`, `in`, `break` and `continue` become keywords: they can no longer be used as names.
- The formatter prints the new statements in the usual layout:

      for x in xs {
          if x == 2 {
              continue;
          }
          break;
      }

  and an empty loop body as `for x in xs {}`, as for `while`.
"""

HIDDEN = r'''
import unittest
from minilang import run, format_source
from minilang.errors import EvalError, ParseError, LexError, LangError


def out(src):
    lines = []
    run(src, lines.append)
    return lines


class Hidden(unittest.TestCase):
    def test_for_list_and_string(self):
        self.assertEqual(out('for x in [1, "a", nil] { print(x); } for c in "hey" { print(c); }'),
                         ["1", "a", "nil", "h", "e", "y"])
        self.assertEqual(out("for x in [] { print(x); } print(1);"), ["1"])

    def test_variable_scope(self):
        self.assertEqual(out("let fs = []; for i in range(3) { push(fs, fn() { return i; }); } "
                             "print(fs[0](), fs[1](), fs[2]());"), ["0 1 2"])
        with self.assertRaises(EvalError):
            out("for i in [1] { } print(i);")
        self.assertEqual(out("let i = 9; for i in [1, 2] { i = i * 10; print(i); } print(i);"), ["10", "20", "9"])
        self.assertEqual(out("let xs = [1, 2]; for x in xs { x = 0; } print(xs);"), ["[1, 2]"])
        with self.assertRaises(EvalError):
            out("for x in [1] { let x = 2; }")
        self.assertEqual(out("for x in [1] { if true { let x = 5; print(x); } print(x); }"), ["5", "1"])

    def test_by_position(self):
        self.assertEqual(out("let xs = [1, 2]; for x in xs { if x < 4 { push(xs, x + 2); } print(x); }"),
                         ["1", "2", "3", "4", "5"])
        self.assertEqual(out("let xs = [1, 2, 3, 4]; for x in xs { pop(xs); print(x); }"), ["1", "2"])

    def test_evaluated_once(self):
        self.assertEqual(out("let n = 0; fn items() { n = n + 1; return [1, 2, 3]; } for x in items() { } print(n);"),
                         ["1"])

    def test_bad_iterable(self):
        for src, word in (("for x in 5 { }", "number"), ("for x in nil { }", "nil"), ("for x in true { }", "bool"),
                          ("for x in print { }", "function")):
            with self.assertRaises(EvalError) as e:
                out(src)
            self.assertIn(f"can't loop over a {word}", str(e.exception))

    def test_break_continue(self):
        self.assertEqual(out("for x in range(10) { if x == 3 { break; } print(x); }"), ["0", "1", "2"])
        self.assertEqual(out("for x in range(5) { if x % 2 == 0 { continue; } print(x); }"), ["1", "3"])
        self.assertEqual(out("let i = 0; while i < 5 { i = i + 1; if i == 2 { continue; } if i == 4 { break; } "
                             "print(i); } print(\"end\", i);"), ["1", "3", "end 4"])
        self.assertEqual(out("for a in [1, 2] { for b in [1, 2, 3] { if b == 2 { break; } print(a, b); } }"),
                         ["1 1", "2 1"])
        self.assertEqual(out("let n = 0; while true { n = n + 1; if n > 3 { break; } } print(n);"), ["4"])

    def test_return_in_loop(self):
        self.assertEqual(out("fn find(xs, y) { for x in xs { if x == y { return \"yes\"; } } return \"no\"; } "
                             "print(find([1, 2], 2), find([1], 3));"), ["yes no"])
        self.assertEqual(out("fn f() { while true { for x in [1] { return x; } } } print(f());"), ["1"])

    def test_outside_loop(self):
        for src, word, line in (("break;", "break", 1), ("let x = 1;\ncontinue;", "continue", 2),
                                ("if true { break; }", "break", 1),
                                ("while true {\n fn f() { break; }\n}", "break", 2),
                                ("for x in [1] { let g = fn() { continue; }; }", "continue", 1)):
            with self.assertRaises(ParseError, msg=src) as e:
                out(src)
            self.assertIn(f"{word} outside a loop", str(e.exception))
            self.assertEqual(e.exception.line, line, src)

    def test_keywords(self):
        for src in ("let for = 1;", "let in = 1;", "let break = 1;", "let continue = 1;"):
            with self.assertRaises(LangError, msg=src):
                out(src)

    def test_formatter(self):
        self.assertEqual(format_source("for x in xs{if x==2{continue;}break;}"),
                         "for x in xs {\n    if x == 2 {\n        continue;\n    }\n    break;\n}\n")
        self.assertEqual(format_source("for c in \"ab\" {}"), "for c in \"ab\" {}\n")
        self.assertEqual(format_source("while a { for b in f(a) { g(b); } }"),
                         "while a {\n    for b in f(a) {\n        g(b);\n    }\n}\n")
        src = "fn f(xs) { for x in xs + [1] { if not x { continue; } else { break; } } }"
        self.assertEqual(format_source(format_source(src)), format_source(src))


if __name__ == "__main__":
    unittest.main()
'''

EXAMPLES = r"""
import re, sys
from pathlib import Path
from minilang import run
folder = Path(sys.argv[1])
parts = re.split(r"^== (\S+)\n", (folder / "expected.txt").read_text(), flags=re.M)[1:]
for name, text in zip(parts[::2], parts[1::2]):
    lines = []
    run((folder / name).read_text(), lines.append)
    assert lines == text.splitlines(), name
"""

def setup(d):
    shutil.copytree(SOURCE, d, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    write(d, "FEATURE.md", FEATURE)

def check(d, answer):
    original = Path(tempfile.mkdtemp())
    setup(original)
    # the original examples must still print what they did (adding or rewriting examples is fine)
    code, out = run([sys.executable, "-B", "-c", EXAMPLES, str(original / "examples")], d,
                    env={"PYTHONPATH": str(d), "PATH": "/usr/bin:/bin"})
    if code != 0:
        return False, "the original examples now print something else: " + out[-300:]
    old_tests = {p.name: p.read_text() for p in (original / "tests").glob("test_*.py")}
    shutil.rmtree(original, ignore_errors=True)
    code, out = run([sys.executable, "-B", "-m", "unittest", "-q"], d)
    if code != 0:
        return False, "tests fail: " + out[-400:]
    tests = Path(d, "tests")
    new = [p for p in tests.rglob("test_*.py") if old_tests.get(p.name) != p.read_text()]
    if not any(word in p.read_text() for p in new for word in ("for ", "break", "continue")):
        return False, "no tests added for the feature"
    hidden = Path(tempfile.mkdtemp()) / "hidden_feature_test.py"
    hidden.write_text(HIDDEN)
    code, out = run([sys.executable, "-B", str(hidden)], d, env={"PYTHONPATH": str(d), "PATH": "/usr/bin:/bin"})
    shutil.rmtree(hidden.parent, ignore_errors=True)
    return code == 0, out[-600:]
