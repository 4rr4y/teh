import json, sys
from datetime import datetime, timedelta
from pathlib import Path
from _lib import write, run, rng

PROMPT = ("The worker crashed overnight and app.log has the details. Find the cause and fix it, so that "
          "`python3 worker.py --check` passes.")
KIND, SIZE, WEB = "dev", "long", False

WORKER = '''"""Sends queued emails. python3 worker.py [--check]"""
import json
import sys


def load_config(path="config.json"):
    with open(path) as f:
        cfg = json.load(f)
    return {
        "batch_size": int(cfg["batch_size"]),
        "retries": int(cfg["retries"]),
        "timeout": float(cfg["timeout"]),
        "smtp_host": cfg["smtp"]["host"],
    }


def main():
    cfg = load_config()
    if "--check" in sys.argv:
        print("config ok:", cfg)
        return
    print("would send emails with", cfg)


if __name__ == "__main__":
    main()
'''
CONFIG = {"batch_size": 50, "retires": 3, "timeout": 30, "smtp": {"host": "mail.internal", "port": 587}}

def log_text():
    r, t, out = rng(61), datetime(2025, 11, 20, 18, 0), []
    for i in range(26_000):
        t += timedelta(seconds=r.randint(1, 3))
        stamp = f"{t:%Y-%m-%d %H:%M:%S},{r.randint(0, 999):03}"
        if i == 17_850:
            out += [f"{stamp} INFO  config: reloading config.json (changed on disk)",
                    f"{stamp} ERROR worker: crashed",
                    "Traceback (most recent call last):",
                    '  File "/srv/worker/worker.py", line 26, in <module>',
                    "    main()",
                    '  File "/srv/worker/worker.py", line 18, in main',
                    "    cfg = load_config()",
                    '  File "/srv/worker/worker.py", line 11, in load_config',
                    '    "retries": int(cfg["retries"]),',
                    "KeyError: 'retries'",
                    f"{stamp} INFO  supervisor: worker exited with status 1; restarting with the last config "
                    "that loaded (from memory)"]
            continue
        kind = r.random()
        if kind < 0.9:
            out.append(f"{stamp} INFO  worker: sent batch {i} ({r.randint(1, 50)} emails) in {r.uniform(0.2, 3):.2f}s")
        elif kind < 0.97:
            out.append(f"{stamp} WARN  smtp: slow response from mail.internal ({r.uniform(5, 25):.1f}s)")
        else:
            out.append(f"{stamp} WARN  worker: retrying batch {i} after timeout")
    out.append(f"{stamp} INFO  supervisor: stopping for maintenance")
    return "\n".join(out) + "\n"

def setup(d):
    write(d, "worker.py", WORKER)
    write(d, "config.json", json.dumps(CONFIG, indent=2) + "\n")
    write(d, "app.log", log_text())

def check(d, answer):
    if Path(d, "worker.py").read_text() != WORKER:
        return False, "worker.py was changed (the cause is in config.json)"
    code, out = run([sys.executable, "-B", "worker.py", "--check"], d)
    if code != 0:
        return False, out[-300:]
    cfg = json.loads(Path(d, "config.json").read_text())
    ok = cfg.get("retries") == 3 and cfg.get("batch_size") == 50 and cfg.get("smtp", {}).get("port") == 587
    return ok, f"config.json: {cfg}"
