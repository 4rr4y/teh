import re

PROMPT = "Look it up on Wikipedia: in what month and year was the Eiffel Tower completed?"
KIND, SIZE, WEB = "everyday", "short", True

def setup(d):
    pass

def check(d, answer):
    ok = "1889" in answer and re.search(r"\bMar(ch)?\b", answer, re.I) is not None
    return ok, "expected March 1889"
