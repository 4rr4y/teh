"""Runs a syntax tree."""
from . import ast
from .builtins import install
from .environment import Environment
from .errors import EvalError
from .operators import binary
from .values import Builtin, Function, is_number, truthy, type_name

MAX_DEPTH = 200  # nested calls, before "too much recursion"


class ReturnSignal(Exception):  # unwinds a function's statements on return
    def __init__(self, value):
        self.value = value


class Interpreter:
    def __init__(self, write=print):
        self.globals = Environment()
        install(self.globals, write)
        self.depth = 0

    def run(self, program):
        for stmt in program.stmts:
            self.execute(stmt, self.globals)

    # ----- Statements -----
    def execute(self, node, env):
        getattr(self, "exec_" + type(node).__name__)(node, env)

    def exec_Let(self, node, env):
        env.define(node.name, self.eval(node.value, env))

    def exec_Assign(self, node, env):
        value = self.eval(node.value, env)
        target = node.target
        if isinstance(target, ast.Name):
            env.assign(target.name, value, target.line)
        else:
            items, index = self.eval(target.target, env), self.eval(target.index, env)
            if not isinstance(items, list):
                raise EvalError(f"can only assign to an index of a list, not of a {type_name(items)}", target.line)
            items[self.position(items, index, target.line)] = value

    def exec_ExprStmt(self, node, env):
        self.eval(node.expr, env)

    def exec_FnDecl(self, node, env):
        env.define(node.name, Function(node.name, node.params, node.body, env))

    def exec_If(self, node, env):
        if truthy(self.eval(node.cond, env)):
            self.exec_Block(node.then, env)
        elif node.else_ is not None:
            self.exec_Block(node.else_, env)

    def exec_While(self, node, env):
        while truthy(self.eval(node.cond, env)):
            self.exec_Block(node.body, env)

    def exec_Return(self, node, env):
        raise ReturnSignal(None if node.value is None else self.eval(node.value, env))

    def exec_Block(self, node, env):
        inner = Environment(env)
        for stmt in node.stmts:
            self.execute(stmt, inner)

    # ----- Expressions -----
    def eval(self, node, env):
        return getattr(self, "eval_" + type(node).__name__)(node, env)

    def eval_Num(self, node, env):
        return node.value

    def eval_Str(self, node, env):
        return node.value

    def eval_Bool(self, node, env):
        return node.value

    def eval_Nil(self, node, env):
        return None

    def eval_Name(self, node, env):
        return env.lookup(node.name, node.line)

    def eval_ListLit(self, node, env):
        return [self.eval(item, env) for item in node.items]

    def eval_FnLit(self, node, env):
        return Function("anonymous", node.params, node.body, env)

    def eval_Index(self, node, env):
        target, index = self.eval(node.target, env), self.eval(node.index, env)
        if not isinstance(target, (list, str)):
            raise EvalError(f"can't index a {type_name(target)}", node.line)
        return target[self.position(target, index, node.line)]

    def eval_Unary(self, node, env):
        value = self.eval(node.operand, env)
        if node.op == "not":
            return not truthy(value)
        if not is_number(value):
            raise EvalError(f"can't negate a {type_name(value)}")
        return -value

    def eval_Binary(self, node, env):
        if node.op == "and":
            left = self.eval(node.left, env)
            return self.eval(node.right, env) if truthy(left) else left
        if node.op == "or":
            left = self.eval(node.left, env)
            return left if truthy(left) else self.eval(node.right, env)
        return binary(node.op, self.eval(node.left, env), self.eval(node.right, env), node.line)

    def eval_Call(self, node, env):
        fn = self.eval(node.callee, env)
        args = [self.eval(arg, env) for arg in node.args]
        if isinstance(fn, Builtin):
            return fn(args, node.line)
        if not isinstance(fn, Function):
            raise EvalError(f"a {type_name(fn)} isn't a function", node.line)
        if len(args) != len(fn.params):
            raise EvalError(f"{fn.name}() takes {len(fn.params)} arguments, got {len(args)}", node.line)
        if self.depth >= MAX_DEPTH:
            raise EvalError("too much recursion", node.line)
        scope = Environment(fn.closure)
        for param, arg in zip(fn.params, args):
            scope.define(param, arg)
        self.depth += 1
        try:
            for stmt in fn.body.stmts:
                self.execute(stmt, scope)
        except ReturnSignal as signal:
            return signal.value
        finally:
            self.depth -= 1
        return None

    @staticmethod
    def position(items, index, line):  # a list or string index, checked; -1 is the last item
        if not isinstance(index, int) or isinstance(index, bool):
            raise EvalError(f"an index must be a whole number, not {type_name(index)}", line)
        if not -len(items) <= index < len(items):
            raise EvalError(f"index {index} out of range for length {len(items)}", line)
        return index
