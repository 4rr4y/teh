"""Prints a hash of everything a test suite depends on: tests/e2e/run.py --changed skips a suite whose hash is the same
as when it last passed. usage: inputs.py SUITE

A suite depends on teh.py (all of it, or only what comes before Part 2, the web helper), its own test script, the fake
servers it starts and the shared helpers. Comments in teh.py don't count, so a comment-only edit reruns nothing. A
dependency missing here would let a breaking change skip a suite, so when in doubt, list it: running a suite too often
only costs time."""
import hashlib
import io
import re
import sys
import tokenize
from pathlib import Path

TESTS = Path(__file__).resolve().parent
HARNESS = TESTS.parent.parent / "teh.py"
FAKES = TESTS.parent / "fakes"
# Where the web helper starts in teh.py
PART_2 = "\n# PART 2"
# These test the web helper too; the others only the harness, Part 1
WHOLE_HARNESS = {"core", "fetch"}
SHARED = ("lib.py", "chat_run.py", "ctrl_c.py", "pty_run.py", "inputs.py")

def code(text):
    """Return Python without its comments, so a comment-only change gives the same hash."""
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        return " ".join(t.string for t in tokens if t.type not in (tokenize.COMMENT, tokenize.NL))
    except (tokenize.TokenError, SyntaxError):
        # Can't be read as Python: all of it counts
        return text

def inputs(suite):
    """Return the texts the suite depends on."""
    harness = HARNESS.read_text(encoding="utf-8")
    if suite not in WHOLE_HARNESS:
        harness = harness[:harness.index(PART_2)]
    script = (TESTS / f"test_{suite}.py").read_text(encoding="utf-8")
    # The fakes it starts, each of which imports common.py
    fakes = set(re.findall(r"\bserve\(\"(\w+\.py)\"", script)) | {"common.py"}
    if ".script(" in script:
        fakes.add("script_server.py")
    return [code(harness), script] + [(TESTS / name).read_text(encoding="utf-8") for name in SHARED] + [
        (FAKES / name).read_text(encoding="utf-8") for name in sorted(fakes)]

def digest(suite):
    """Return a short hash of everything the suite depends on."""
    return hashlib.sha256("\0".join(inputs(suite)).encode()).hexdigest()[:16]

if __name__ == "__main__":
    print(digest(sys.argv[1]))
