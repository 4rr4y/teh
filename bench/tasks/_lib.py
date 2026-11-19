"""Helpers shared by the benchmark tasks.

A task is a module in this folder (files starting with _ are not tasks) with:
  PROMPT     what the user asks, as given to teh
  KIND       "dev" (a developer's task) or "everyday" (anyone's: files, data, documents, questions)
  SIZE       "short", "slow", "long" or "xl" (slow ones have commands that take a while, for what running them in
             parallel saves; long ones grow the context; xl ones make the model read or write a lot over many calls, to
             reach the context sizes where compaction acts)
  WEB        True if it needs the internet (skipped unless the runner is given --web)
  setup(d)   creates the task's files in the empty folder d (a pathlib.Path); data is generated from a fixed seed,
             so every run, and the checker, sees the same
  check(d, answer) -> (passed, detail)   d after the run, answer: teh's final reply. Never shown to the model
"""
import hashlib, random, re, subprocess, sys
from pathlib import Path

def write(d, name, text):  # a file under d, with its folders
    path = Path(d, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path

def numbers(text):  # every number in text: 1,234.50 -> 1234.5; £, $ and the like are ignored
    found = []
    for raw in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text):
        try:
            found.append(float(raw.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return found

def has_number(text, value, tolerance=0.0):
    return any(abs(n - value) <= tolerance for n in numbers(text))

def digest(path):  # a hash of a file, or of every file in a folder (names and contents), to tell if it changed
    path, h = Path(path), hashlib.sha256()
    files = sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts) \
        if path.is_dir() else [path]
    for f in files:
        h.update(str(f.relative_to(path) if path.is_dir() else f.name).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()

def run(cmd, cwd, timeout=120, **kw):  # -> (exit code, output); a timeout counts as a failure
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, **kw)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {timeout}s"

def python(code, cwd, timeout=120):  # run Python code in cwd, with cwd importable
    return run([sys.executable, "-B", "-c", code], cwd, timeout)

WORDS = ("the of and to in a is that for it as with be on not this are by at or from have an they which you were "
         "all their has would will there been one more if can its also when who other any these may such only "
         "time after should under where between each those both while same during within without against "
         "service account policy team request approval manager staff office record data period process review "
         "member customer report system support access change notice year month week day agreement section "
         "required provided including applicable relevant appropriate reasonable written internal external").split()

def filler(rng, sentences):  # plausible-looking but meaningless sentences, for bulk text around the facts
    out = []
    for _ in range(sentences):
        words = [rng.choice(WORDS) for _ in range(rng.randint(8, 20))]
        out.append(" ".join(words).capitalize() + ".")
    return out

def rng(seed):
    return random.Random(seed)
