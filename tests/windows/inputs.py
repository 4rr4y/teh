"""Prints a hash of everything a Windows test suite depends on: tests/windows/run.py --changed skips a suite whose hash
is the same as when it last passed. usage: inputs.py SUITE

As tests/unix/inputs.py: a suite depends on teh.py (all of it, or only what comes before Part 2, the web helper), its
own test script, the fake servers it starts and the shared helpers. Comments in teh.py don't count. A dependency
missing here would let a breaking change skip a suite, so when in doubt, list it."""
import hashlib, io, re, sys, tokenize
from pathlib import Path

TESTS = Path(__file__).resolve().parent
HARNESS = TESTS.parent.parent / "teh.py"
FAKES = TESTS.parent / "fakes"  # shared
PART_2 = "\n# PART 2"           # where the web helper starts in teh.py
WHOLE_HARNESS = {"core", "fetch"}  # these test the web helper too; the others only the harness, Part 1
SHARED = ("lib.py", "chat_run.py", "ctrl_c.py", "inputs.py")

def code(text):  # Python without its comments, so a comment-only change gives the same hash
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        return " ".join(t.string for t in tokens if t.type not in (tokenize.COMMENT, tokenize.NL))
    except (tokenize.TokenError, SyntaxError):  # can't be read as Python: all of it counts
        return text

def inputs(suite):  # -> the texts the suite depends on
    harness = HARNESS.read_text(encoding="utf-8")
    if suite not in WHOLE_HARNESS:
        harness = harness[:harness.index(PART_2)]
    script = (TESTS / f"test_{suite}.py").read_text(encoding="utf-8")
    fakes = set(re.findall(r"\bserve\(\"(\w+\.py)\"", script)) | ({"script_server.py"} if ".script(" in script else set())
    return [code(harness), script] + [(TESTS / name).read_text(encoding="utf-8") for name in SHARED] + [
        (FAKES / name).read_text(encoding="utf-8") for name in sorted(fakes)]

def digest(suite):
    return hashlib.sha256("\0".join(inputs(suite)).encode()).hexdigest()[:16]

if __name__ == "__main__":
    print(digest(sys.argv[1]))
