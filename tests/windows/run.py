"""Runs the Windows test suites: python tests\\windows\\run.py [--changed] [suite ...]   e.g. run.py core fetch
  --changed  skips a suite when nothing it depends on has changed since it last passed (see inputs.py). The unit tests
             always run: they take a few seconds.
Needs Windows and Python 3.10 or later, nothing else: no API key, no network. The suites run the model's commands in
cmd and Windows PowerShell, and in PowerShell 7 (pwsh) too where it's installed."""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITES = ["units", "core", "chat", "caching", "errors", "output", "compact", "fetch"]
PASSED = HERE / ".passed"  # one line per suite: its name and the hash of its inputs when it last passed

def main(args):
    if sys.platform != "win32":
        sys.exit("the Windows suites need Windows: on Linux or macOS, run tests/unix/run.sh")
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
                               capture_output=True, text=True)  # shared with other systems
            out = p.stdout + p.stderr
            print("\n".join(out.strip().splitlines()[-3:]) if p.returncode == 0 else out, flush=True)  # a failure: all
        else:
            key = digest(suite)
            if changed and passed.get(suite) == key:
                skipped.append(suite)
                continue
            print(f"######## {suite}", flush=True)
            p = subprocess.run([sys.executable, "-B", str(HERE / f"test_{suite}.py")], cwd=HERE)
            if p.returncode == 0:  # remember it passed with these inputs
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
