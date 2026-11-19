PROMPT = "According to PyPI, which licence is the Python package requests released under?"
KIND, SIZE, WEB = "dev", "short", True

def setup(d):
    pass

def check(d, answer):
    return "apache" in answer.lower(), "expected Apache 2.0"
