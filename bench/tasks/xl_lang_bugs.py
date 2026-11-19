import shutil, sys, tempfile
from pathlib import Path
from _lib import digest, run, python

PROMPT = ("minilang is a small scripting language (see LANGUAGE.md). Its test suite (python3 -m unittest) fails. "
          "Find and fix the bugs in the interpreter so that all the tests pass. Don't change the tests or the "
          "examples.")
KIND, SIZE, WEB = "dev", "xl", False
SOURCE = Path(__file__).parent / "_minilang"

# Each bug: (file, the correct code, the buggy code). LANGUAGE.md describes the correct behaviour.
BUGS = [
    ("minilang/lexer.py", '            out.append(ESCAPES[src[i + 1]])\n            i += 2\n',
     '            out.append(ESCAPES[src[i + 1]])\n            i += 1\n'),
    ("minilang/parser.py", "UNARY = 7  #", "UNARY = 9  #"),
    ("minilang/interpreter.py", "env.define(node.name, Function(node.name, node.params, node.body, env))",
     "env.define(node.name, Function(node.name, node.params, node.body, self.globals))"),
    ("minilang/builtins.py", "    while (x < stop) if step > 0 else (x > stop):",
     "    while (x <= stop) if step > 0 else (x > stop):"),
    ("minilang/formatter.py", "right = expr(node.right, depth, prec if right_assoc else prec + 1)",
     "right = expr(node.right, depth, prec)"),
]

HIDDEN = r'''
from minilang import run, format_source
from minilang.lexer import tokenize
def out(src):
    lines = []
    run(src, lines.append)
    return lines
assert [t.value for t in tokenize(r'"a\\b" "\"" "x\ty"')][:3] == ["a\\b", '"', "x\ty"]
assert out(r'print(len("\\"), len("a\"b"));') == ["1 3"], "escapes"
assert out("print(-3 ^ 2, 2 ^ -1, -2 * 3, not true == false);") == ["-9 0.5 -6 true"], "unary"
assert out("""
let fs = [];
fn make(k) { fn get() { return k * 10; } return get; }
let i = 0;
while i < 3 { push(fs, make(i)); i = i + 1; }
print(fs[0](), fs[2]());
fn outer() { let total = 0; fn add(n) { total = total + n; } add(2); add(5); return total; }
print(outer());
""") == ["0 20", "7"], "closures"
assert out("print(range(5), range(2, 5), range(5, 2, -1), range(3, 3), range(0, 6, 2));") == \
    ["[0, 1, 2, 3, 4] [2, 3, 4] [5, 4, 3] [] [0, 2, 4]"], "range"
for src, want in [("x = a / (b * c);", "x = a / (b * c);\n"), ("x = a - (b + c);", "x = a - (b + c);\n"),
                  ("x = (a * b) / c;", "x = a * b / c;\n"), ("x = 2 ^ (3 ^ 2);", "x = 2 ^ 3 ^ 2;\n"),
                  ("x = (2 ^ 3) ^ 2;", "x = (2 ^ 3) ^ 2;\n"),
                  ("x = -(a - b);", "x = -(a - b);\n"), ("x = not (a == b);", "x = not (a == b);\n")]:
    assert format_source(src) == want, (src, format_source(src))
print("ok")
'''

def setup(d):
    shutil.copytree(SOURCE, d, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    for name, good, bad in BUGS:
        path = Path(d, name)
        text = path.read_text()
        assert text.count(good) == 1, (name, good)
        path.write_text(text.replace(good, bad))

def check(d, answer):
    original = Path(tempfile.mkdtemp())
    setup(original)
    for folder in ("tests", "examples"):
        if digest(Path(d, folder)) != digest(original / folder):
            return False, f"{folder}/ was changed"
    shutil.rmtree(original, ignore_errors=True)
    code, out = run([sys.executable, "-B", "-m", "unittest", "-q"], d)
    if code != 0:
        return False, "tests fail: " + out[-400:]
    code, out = python(HIDDEN, d)
    return code == 0, out[-300:]
