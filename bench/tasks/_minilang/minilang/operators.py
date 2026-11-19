"""What the binary operators do. "and" and "or" aren't here: the interpreter evaluates their right side only when
needed."""
from .errors import EvalError
from .values import equal, is_number, show, type_name

COMPARISONS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}


def binary(op, a, b, line=None):
    if op == "==":
        return equal(a, b)
    if op == "!=":
        return not equal(a, b)
    if op in COMPARISONS:
        if (is_number(a) and is_number(b)) or (isinstance(a, str) and isinstance(b, str)):
            return COMPARISONS[op](a, b)
        raise EvalError(f"can't compare {type_name(a)} and {type_name(b)} with {op}", line)
    if op == "+" and isinstance(a, str) and isinstance(b, str):
        return a + b
    if op == "+" and isinstance(a, list) and isinstance(b, list):
        return a + b
    if op == "*" and isinstance(a, str) and isinstance(b, int) and not isinstance(b, bool):
        return a * max(b, 0)
    if not (is_number(a) and is_number(b)):
        raise EvalError(f"can't use {op} on {type_name(a)} and {type_name(b)}", line)
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op in ("/", "%") and b == 0:
        raise EvalError("division by zero" if op == "/" else "modulo by zero", line)
    if op == "/":  # whole numbers stay whole when they divide exactly: 6 / 3 is 2, 7 / 2 is 3.5
        return a // b if isinstance(a, int) and isinstance(b, int) and a % b == 0 else a / b
    if op == "%":
        return a % b
    if op == "^":
        if isinstance(a, int) and isinstance(b, int) and b >= 0:
            return a ** b
        if a < 0 and b != int(b):
            raise EvalError(f"can't raise the negative number {show(a)} to {show(b)}", line)
        return float(a) ** b
    raise EvalError(f"unknown operator {op}", line)
