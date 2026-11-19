"""minilang: a small scripting language. See LANGUAGE.md."""
from .lexer import tokenize
from .parser import parse
from .interpreter import Interpreter
from .formatter import format_source


def run(source, write=print):
    """Runs a program; print() output goes to write (one call per line, without the newline)."""
    interpreter = Interpreter(write)
    interpreter.run(parse(tokenize(source)))
    return interpreter
