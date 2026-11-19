"""Turns source text into tokens."""
from dataclasses import dataclass

from .errors import LexError

KEYWORDS = {"let", "fn", "return", "if", "else", "while", "true", "false", "nil", "and", "or", "not"}
# Longest first, so that "<=" isn't read as "<" and "="
SYMBOLS = ["==", "!=", "<=", ">=", "+", "-", "*", "/", "%", "^", "<", ">", "=", "(", ")", "{", "}", "[", "]", ",",
           ";"]
ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


@dataclass
class Token:
    kind: str  # "num", "str", "name", "kw" (a keyword), "op" (a symbol) or "eof"
    value: object
    line: int


def tokenize(src):
    tokens, i, line = [], 0, 1
    while i < len(src):
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif c == "#":  # a comment, to the end of the line
            while i < len(src) and src[i] != "\n":
                i += 1
        elif c.isdigit():
            i = _number(src, i, line, tokens)
        elif c.isalpha() or c == "_":
            j = i
            while j < len(src) and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            tokens.append(Token("kw" if word in KEYWORDS else "name", word, line))
            i = j
        elif c == '"':
            i, text = _string(src, i + 1, line)
            tokens.append(Token("str", text, line))
        else:
            for symbol in SYMBOLS:
                if src.startswith(symbol, i):
                    tokens.append(Token("op", symbol, line))
                    i += len(symbol)
                    break
            else:
                raise LexError(f"unexpected character {c!r}", line)
    tokens.append(Token("eof", None, line))
    return tokens


def _number(src, i, line, tokens):  # 12, 3.25; "3." and ".5" aren't numbers
    j = i
    while j < len(src) and src[j].isdigit():
        j += 1
    if j + 1 < len(src) and src[j] == "." and src[j + 1].isdigit():
        j += 1
        while j < len(src) and src[j].isdigit():
            j += 1
    if j < len(src) and (src[j].isalpha() or src[j] == "_"):
        raise LexError(f"bad number {src[i:j + 1]!r}", line)
    text = src[i:j]
    tokens.append(Token("num", float(text) if "." in text else int(text), line))
    return j


def _string(src, i, line):  # i is just after the opening quote -> (index after the closing quote, the text)
    out = []
    while i < len(src):
        c = src[i]
        if c == '"':
            return i + 1, "".join(out)
        if c == "\n":
            break
        if c == "\\":
            if i + 1 >= len(src) or src[i + 1] not in ESCAPES:
                raise LexError("bad escape in string: use \\n, \\t, \\\" or \\\\", line)
            out.append(ESCAPES[src[i + 1]])
            i += 2
        else:
            out.append(c)
            i += 1
    raise LexError("unterminated string", line)
