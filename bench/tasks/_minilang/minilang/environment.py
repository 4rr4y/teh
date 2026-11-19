"""Scopes: each block and each function call gets one, chained to the scope it was created in."""
from .errors import EvalError


class Environment:
    def __init__(self, parent=None):
        self.vars, self.parent = {}, parent

    def define(self, name, value):  # let: a new variable here, hiding any outer one
        if name in self.vars:
            raise EvalError(f"{name!r} is already defined in this scope")
        self.vars[name] = value

    def lookup(self, name, line=None):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise EvalError(f"undefined name {name!r}", line)

    def assign(self, name, value, line=None):  # x = ...: the nearest existing variable
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        raise EvalError(f"assignment to undefined name {name!r}: declare it with let first", line)
