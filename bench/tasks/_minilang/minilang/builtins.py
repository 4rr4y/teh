"""The functions every program can call."""
from .errors import EvalError
from .values import Builtin, is_number, show, type_name


def install(env, write):
    def print_(*args):
        write(" ".join(show(a) for a in args))

    for name, fn, arity in [("print", print_, None), ("len", length, 1), ("str", lambda x: show(x), 1),
                            ("num", to_number, 1), ("type", type_name, 1), ("range", range_, None),
                            ("push", push, 2), ("pop", pop, 1), ("join", join, 2), ("split", split, 2),
                            ("abs", absolute, 1), ("min", minimum, None), ("max", maximum, None)]:
        env.define(name, Builtin(name, fn, arity))


def length(x):
    if not isinstance(x, (str, list)):
        raise EvalError(f"len() needs a string or a list, not {type_name(x)}")
    return len(x)


def to_number(s):
    if is_number(s):
        return s
    if isinstance(s, str):
        for kind in (int, float):
            try:
                return kind(s.strip())
            except ValueError:
                pass
    raise EvalError(f"num(): not a number: {show(s, True)}")


def range_(*args):  # range(n): 0 to n-1; range(a, b): a to b-1; range(a, b, step)
    if not 1 <= len(args) <= 3 or not all(isinstance(a, int) and not isinstance(a, bool) for a in args):
        raise EvalError("range() takes 1 to 3 whole numbers")
    start, stop, step = (0, args[0], 1) if len(args) == 1 else (args[0], args[1], args[2] if len(args) == 3 else 1)
    if step == 0:
        raise EvalError("range(): step can't be 0")
    out, x = [], start
    while (x < stop) if step > 0 else (x > stop):
        out.append(x)
        x += step
    return out


def push(items, x):  # adds x to the end of the list, and returns the list
    _need_list("push", items)
    items.append(x)
    return items


def pop(items):  # removes the last item, and returns it
    _need_list("pop", items)
    if not items:
        raise EvalError("pop() from an empty list")
    return items.pop()


def join(items, sep):
    _need_list("join", items)
    if not isinstance(sep, str):
        raise EvalError("join(): the separator must be a string")
    return sep.join(show(x) for x in items)


def split(s, sep):
    if not isinstance(s, str) or not isinstance(sep, str) or not sep:
        raise EvalError("split() needs a string and a non-empty separator")
    return s.split(sep)


def absolute(x):
    if not is_number(x):
        raise EvalError(f"abs() needs a number, not {type_name(x)}")
    return abs(x)


def minimum(*args):
    return _extreme("min", args, min)


def maximum(*args):
    return _extreme("max", args, max)


def _extreme(name, args, pick):  # min(1, 2, 3) or min([1, 2, 3])
    values = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
    if not values or not all(is_number(v) for v in values):
        raise EvalError(f"{name}() needs numbers")
    return pick(values)


def _need_list(name, x):
    if not isinstance(x, list):
        raise EvalError(f"{name}() needs a list, not {type_name(x)}")
