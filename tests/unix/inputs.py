"""Prints a hash of everything a test suite depends on: tests/unix/run.sh --changed skips a suite whose hash is the same as
when it last passed. usage: inputs.py SUITE (from tests/unix/run.sh)

A suite depends on teh.py (all of it, or only what comes before Part 2, the web helper), its own test script, the
fake servers it starts (found from its `serve` lines) and the shared helpers. Comments in teh.py don't count, so a
comment-only edit reruns nothing. A dependency missing here would let a breaking change skip a suite, so when in
doubt, list it: running a suite too often only costs time."""
import hashlib, io, re, sys, tokenize
from pathlib import Path

TESTS = Path(__file__).resolve().parent
HARNESS = TESTS.parent.parent / "teh.py"
FAKES = TESTS.parent / "fakes"  # shared
PART_2 = "\n# PART 2"           # where the web helper starts in teh.py
WHOLE_HARNESS = {"core", "fetch"}  # these test the web helper too; the others only the harness, Part 1
SHARED = ("lib.sh", "pty_run.py")

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
    script = (TESTS / f"test_{suite}.sh").read_text(encoding="utf-8")
    fakes = sorted(set(re.findall(r"\bserve (\w+\.py)", script)))
    return [code(harness), script] + [(TESTS / name).read_text(encoding="utf-8") for name in SHARED] + [
        (FAKES / name).read_text(encoding="utf-8") for name in fakes]

if __name__ == "__main__":
    print(hashlib.sha256("\0".join(inputs(sys.argv[1])).encode()).hexdigest()[:16])
