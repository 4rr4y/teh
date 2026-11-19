"""Runtime values: minilang's nil, booleans, numbers, strings and lists are Python's None, bool, int/float, str and
list. Functions are Function or Builtin."""
from .errors import EvalError


class Function:
    def __init__(self, name, params, body, closure):
        self.name, self.params, self.body, self.closure = name, params, body, closure

    def __repr__(self):
        return f"<fn {self.name}>"


class Builtin:
    def __init__(self, name, fn, arity=None):  # arity None: any number of arguments
        self.name, self.fn, self.arity = name, fn, arity

    def __call__(self, args, line=None):
        if self.arity is not None and len(args) != self.arity:
            raise EvalError(f"{self.name}() takes {self.arity} argument{'s' * (self.arity != 1)}, got {len(args)}",
                            line)
        return self.fn(*args)

    def __repr__(self):
        return f"<builtin {self.name}>"


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def truthy(x):  # only false and nil are false: 0, "" and [] are true
    return x is not None and x is not False


def type_name(x):
    if x is None:
        return "nil"
    if isinstance(x, bool):
        return "bool"
    if is_number(x):
        return "number"
    if isinstance(x, str):
        return "string"
    if isinstance(x, list):
        return "list"
    return "function"


def equal(a, b):  # numbers compare by value (1 == 1.0); otherwise values of different types are never equal
    if is_number(a) and is_number(b):
        return a == b
    if type_name(a) != type_name(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    return a is b if type_name(a) == "function" else a == b


def show(x, nested=False):  # how print() and str() show a value; strings are quoted inside lists
    if x is None:
        return "nil"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, float):
        return repr(x)
    if isinstance(x, str):
        return quote(x) if nested else x
    if isinstance(x, list):
        return "[" + ", ".join(show(item, True) for item in x) + "]"
    return repr(x)


def quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'
