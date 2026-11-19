"""Runs the test suites: python tests/e2e/run.py [--changed] [suite ...]   e.g. run.py core fetch
  --changed  skips a suite when nothing it depends on has changed since it last passed (see inputs.py). The unit tests
             always run: they take a few seconds.
Needs Python 3.10 or later, nothing else: no API key, no network. Runs on Linux, macOS and Windows; the suites run the
model's commands in the system's shells (see SHELLS in lib.py)."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITES = ["units", "core", "chat", "caching", "errors", "output", "compact", "fetch"]
# One line per suite: its name and the hash of its inputs when it last passed
PASSED = HERE / ".passed"

def main(args):
    """Run the suites args names (all by default); return the exit code: 1 if any failed."""
    changed = args[:1] == ["--changed"]
    suites = args[1:] if changed else args
    suites = suites or SUITES
    if unknown := [x for x in suites if x not in SUITES]:
        sys.exit(f"unknown suite {', '.join(unknown)}: the suites are {', '.join(SUITES)}")
    sys.path.insert(0, str(HERE))
    from inputs import digest
    passed = dict(line.split() for line in PASSED.read_text().splitlines() if line.strip()) if PASSED.exists() else {}
    failed, skipped = [], []
    for suite in suites:
        if suite == "units":
            print("######## units", flush=True)
            p = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", "test_units"], cwd=HERE.parent,
                               capture_output=True, text=True, check=False)
            out = p.stdout + p.stderr
            # A failure is shown whole, to see which test and why
            print("\n".join(out.strip().splitlines()[-3:]) if p.returncode == 0 else out, flush=True)
        else:
            key = digest(suite)
            if changed and passed.get(suite) == key:
                skipped.append(suite)
                continue
            print(f"######## {suite}", flush=True)
            p = subprocess.run([sys.executable, "-B", str(HERE / f"test_{suite}.py")], cwd=HERE, check=False)
            # Remember it passed with these inputs
            if p.returncode == 0:
                passed[suite] = key
                PASSED.write_text("".join(f"{k} {v}\n" for k, v in sorted(passed.items())))
        if p.returncode != 0:
            failed.append(suite)
    print()
    if skipped:
        print(f"skipped (nothing they depend on changed since they passed): {' '.join(skipped)}")
    if failed:
        print(f"FAILED: {' '.join(failed)}")
        return 1
    print("all suites passed")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
