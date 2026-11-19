"""The errors a program can raise: all are LangError, so callers can catch them together."""


class LangError(Exception):
    def __init__(self, message, line=None):
        super().__init__(f"line {line}: {message}" if line else message)
        self.message, self.line = message, line


class LexError(LangError):
    """Bad characters, strings or numbers in the source."""


class ParseError(LangError):
    """Source that doesn't follow the grammar."""


class EvalError(LangError):
    """Errors while running: wrong types, undefined names, bad indexes and the like."""
