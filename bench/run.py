#!/usr/bin/env python3
"""Runs teh on the benchmark's tasks and checks the results. See bench/README.md.

usage: bench/run.py [--tasks NAME ...] [--config NAME [TEH_X=VALUE ...]] ... [--repeat N] [-j N] [--web]
                    [--name RUN] [--keep]

The model is set as for teh itself, with TEH_BASE_URL, TEH_MODEL, TEH_API_KEY (and TEH_EFFORT and the like) in the
environment. Each --config is a name and the TEH_ settings it adds or changes, e.g.
--config compact20k TEH_CONTEXT_WINDOW=20000; without one, a single config, "baseline", runs teh as it is. A config
may also name another copy of teh to run, HARNESS=path/to/teh.py, to compare two versions on the same day. Results go
to bench/results/RUN/: results.jsonl (one line per run of a task), and for each run its log (teh's stderr) and trace
(every model call, recorded by a proxy between teh and the API). A run already in results.jsonl is skipped, so an interrupted run can be resumed with the same --name.

Every model call goes through a small proxy on localhost, which passes it on unchanged and records its token usage:
cache writes and reads included, which teh's own JSON summary doesn't separate.
"""
import argparse, concurrent.futures, fnmatch, importlib.util, json, os, signal, subprocess, sys, tempfile
import threading, time, urllib.error, urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BENCH = Path(__file__).resolve().parent
HARNESS = BENCH.parent / "teh.py"
TASKS = BENCH / "tasks"
GUARDS = {"TEH_TURN_BUDGET": "80", "TEH_TOKEN_BUDGET": "4000000", "TEH_COMMAND_TIMEOUT": "120"}  # per run; a
TIMEOUTS = {"short": 600, "slow": 900, "long": 1500, "xl": 2700}  # seconds for a whole run           # config can change them
TURNS = {"xl": "150"}  # model calls, where the size needs more than the guard above

def load_harness():  # teh.py as a module: it has no side effects on import
    spec = importlib.util.spec_from_file_location("teh", HARNESS)
    module = importlib.util.module_from_spec(spec)
    sys.modules["teh"] = module  # its dataclasses look themselves up there
    spec.loader.exec_module(module)
    return module

def load_tasks(patterns, web=False):  # -> {name: module}, in name order
    sys.path.insert(0, str(TASKS))
    tasks = {}
    for path in sorted(TASKS.glob("[!_]*.py")):
        if not any(fnmatch.fnmatch(path.stem, p) for p in patterns):
            continue
        spec = importlib.util.spec_from_file_location(f"task_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if module.WEB and not web and patterns == ["*"]:
            continue  # web tasks only when asked for, by --web or by name
        tasks[path.stem] = module
    return tasks

# ===== The recording proxy =========================================================================================
# teh is pointed at http://127.0.0.1:PORT/https/api.anthropic.com/v1: the upstream's host stays in the URL, so teh still
# recognises the provider (its API format and PROVIDER_QUIRKS go by the URL)
def usage_of(path, reply, headers, harness):  # -> {"in", "uncached", "write", "read", "out"} in tokens
    u = reply.get("usage") or {}
    if path.endswith("/messages"):  # Anthropic
        write, read = u.get("cache_creation_input_tokens") or 0, u.get("cache_read_input_tokens") or 0
        uncached = u.get("input_tokens") or 0
        return {"in": uncached + write + read, "uncached": uncached, "write": write, "read": read,
                "out": u.get("output_tokens") or 0}
    total = u.get("prompt_tokens") or 0
    read = harness.cached_tokens(u) or int(headers.get("fireworks-cached-prompt-tokens") or 0)
    return {"in": total, "uncached": total - read, "write": 0, "read": read, "out": u.get("completion_tokens") or 0}

def message_sizes(body):  # the request's messages as [kind, characters]: u prompt, a reply, t command output
    sizes = []
    for m in body.get("messages", []):
        content = m.get("content")
        if m["role"] == "tool":
            sizes.append(["t", len(content or "")])
        elif m["role"] == "user" and isinstance(content, list):
            sizes += [["t", len(json.dumps(b.get("content")))] for b in content if b.get("type") == "tool_result"]
        elif m["role"] in ("user", "assistant"):
            sizes.append([m["role"][0], len(json.dumps(content)) + len(json.dumps(m.get("tool_calls") or ""))])
    return sizes

class Proxy(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["content-length"]))
        scheme, host, rest = self.path.lstrip("/").split("/", 2)
        url = f"{scheme}://{host}/{rest}"
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "content-length", "connection", "accept-encoding")}
        start = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=600) as r:
                status, data, reply_headers = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            status, data, reply_headers = e.code, e.read(), e.headers
        except Exception as e:  # network: teh sees a 502 and retries as it would
            status, data, reply_headers = 502, json.dumps({"error": f"proxy: {e}"}).encode(), {}
        self.server.record(url, json.loads(body), status, data, reply_headers, time.monotonic() - start)
        self.send_response(status)
        for name in ("content-type", "retry-after", "retry-after-ms", "fireworks-cached-prompt-tokens"):
            if reply_headers.get(name):
                self.send_header(name, reply_headers[name])
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass

class Recorder(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, trace, harness):
        super().__init__(("127.0.0.1", 0), Proxy)
        self.trace, self.harness, self.calls, self.lock = trace, harness, [], threading.Lock()

    def record(self, url, body, status, data, headers, seconds):
        call = {"status": status, "seconds": round(seconds, 2), "messages": message_sizes(body),
                "request_chars": len(json.dumps(body))}
        if status == 200:
            reply = json.loads(data)
            call["usage"] = usage_of(url, reply, headers, self.harness)
            call["stop"] = reply.get("stop_reason") or (reply.get("choices") or [{}])[0].get("finish_reason")
        else:
            call["error"] = data[:500].decode(errors="replace")
        with self.lock:
            self.calls.append(call)
            with open(self.trace, "a") as f:
                f.write(json.dumps(call) + "\n")

# ===== Running one task ============================================================================================
def run_one(task_name, task, config, overrides, rep, out, model_env, upstream):
    overrides = dict(overrides)
    harness = Path(overrides.pop("HARNESS", HARNESS)).resolve()  # this config's copy of teh (default: teh.py)
    work = Path(tempfile.mkdtemp(prefix=f"teh-bench-{task_name}-"))
    task.setup(work)
    stem = f"{config}/{task_name}-{rep}"
    (out / "logs" / config).mkdir(parents=True, exist_ok=True)
    (out / "traces" / config).mkdir(parents=True, exist_ok=True)
    trace, log = out / "traces" / f"{stem}.jsonl", out / "logs" / f"{stem}.log"
    trace.unlink(missing_ok=True)
    proxy = Recorder(trace, HARNESS_MODULE)
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    scheme, rest = upstream.split("://", 1)
    env = {k: v for k, v in os.environ.items() if not k.startswith("TEH_")}
    env.update(model_env)
    env.update(GUARDS)
    if task.SIZE in TURNS:
        env["TEH_TURN_BUDGET"] = TURNS[task.SIZE]
    env.update(TEH_BASE_URL=f"http://127.0.0.1:{proxy.server_address[1]}/{scheme}/{rest}", TEH_AUTO="1",
               TEH_OUTPUT="json")
    env.update(overrides)
    timeout = getattr(task, "TIMEOUT", TIMEOUTS[task.SIZE])
    start, result = time.monotonic(), {}
    with open(log, "w") as stderr:
        p = subprocess.Popen([sys.executable, "-B", str(harness), task.PROMPT], cwd=work, env=env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr, text=True,
                             start_new_session=True)  # no terminal: teh can't open /dev/tty
        try:
            stdout, _ = p.communicate(timeout=timeout)
            result = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else {}
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.communicate()
            result = {"ended": "timeout"}
        except json.JSONDecodeError:
            result = {"ended": "bad_output"}
    seconds = time.monotonic() - start
    proxy.shutdown()
    try:
        passed, detail = task.check(work, result.get("answer") or "")
    except Exception as e:  # a crash in the checker is a failed run, with the reason
        passed, detail = False, f"checker error: {type(e).__name__}: {e}"
    calls = [c for c in proxy.calls if "usage" in c]
    totals = {k: sum(c["usage"][k] for c in calls) for k in ("in", "uncached", "write", "read", "out")}
    record = {"config": config, "task": task_name, "rep": rep, "kind": task.KIND, "size": task.SIZE,
              "passed": bool(passed), "detail": str(detail)[:500], "ended": result.get("ended"),
              "answer": (result.get("answer") or "")[:2000],
              "seconds": round(seconds, 1), "calls": len(calls), "errors": len(proxy.calls) - len(calls),
              "max_context": max((c["usage"]["in"] for c in calls), default=0), **totals,
              "commands": len(result.get("commands") or []), "compactions": result.get("compactions", 0),
              "overrides": overrides}
    if not KEEP:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    else:
        record["workdir"] = str(work)
    return record

# ===== Main ========================================================================================================
KEEP = False
HARNESS_MODULE = None

def main():
    global KEEP, HARNESS_MODULE
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tasks", nargs="+", default=["*"], help="task names or patterns (default: all but web)")
    parser.add_argument("--config", nargs="+", action="append", metavar=("NAME", "TEH_X=VALUE"),
                        help="a config to compare: its name and the settings it changes (repeatable)")
    parser.add_argument("--repeat", type=int, default=1, help="runs of each task per config (default 1)")
    parser.add_argument("-j", "--jobs", type=int, default=4, help="runs at the same time (default 4)")
    parser.add_argument("--web", action="store_true", help="include the tasks that need the internet")
    parser.add_argument("--name", help="results folder name (default: the date and time)")
    parser.add_argument("--keep", action="store_true", help="keep each run's working folder, to look at")
    args = parser.parse_args()
    KEEP, HARNESS_MODULE = args.keep, load_harness()

    base = os.environ.get("TEH_BASE_URL", "").strip()
    upstream = HARNESS_MODULE.PROVIDERS.get(base.lower(), base).rstrip("/")
    if not (upstream.startswith(("http://", "https://")) and os.environ.get("TEH_MODEL")):
        sys.exit("set TEH_BASE_URL, TEH_MODEL and TEH_API_KEY as for teh (see bench/README.md)")
    model_env = {k: v for k, v in os.environ.items() if k.startswith("TEH_") and k != "TEH_BASE_URL"}
    model_env.setdefault("TEH_FORMAT", "anthropic" if "anthropic" in upstream else "openai")

    configs = {}
    for name, *settings in args.config or [["baseline"]]:
        bad = [s for s in settings if "=" not in s or not s.startswith(("TEH_", "HARNESS="))]
        if bad:
            sys.exit(f"--config {name}: settings must look like TEH_X=VALUE or HARNESS=path, not {bad}")
        for s in settings:
            if s.startswith("HARNESS=") and not Path(s.split("=", 1)[1]).is_file():
                sys.exit(f"--config {name}: no such file {s.split('=', 1)[1]}")
        configs[name] = dict(s.split("=", 1) for s in settings)
    tasks = load_tasks(args.tasks, args.web)
    if not tasks:
        sys.exit(f"no tasks match {args.tasks}")

    out = BENCH / "results" / (args.name or datetime.now().strftime("%Y%m%d-%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    results = out / "results.jsonl"
    done = set()
    if results.exists():
        for line in results.read_text().splitlines():
            r = json.loads(line)
            done.add((r["config"], r["task"], r["rep"]))
    meta = {"model": os.environ["TEH_MODEL"], "upstream": upstream, "effort": os.environ.get("TEH_EFFORT"),
            "configs": configs, "harness_mtime": HARNESS.stat().st_mtime, "started": datetime.now().isoformat()}
    (out / "meta.json").write_text(json.dumps(meta, indent=2))

    jobs = [(t, c, rep) for rep in range(1, args.repeat + 1) for t in tasks for c in configs
            if (c, t, rep) not in done]
    print(f"{len(jobs)} runs ({len(done)} already done) of {len(tasks)} tasks × {len(configs)} configs × "
          f"{args.repeat}, {args.jobs} at a time; results in {out}", file=sys.stderr)
    lock = threading.Lock()
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        futures = {pool.submit(run_one, t, tasks[t], c, configs[c], rep, out, model_env, upstream): (t, c, rep)
                   for t, c, rep in jobs}
        try:
            for future in concurrent.futures.as_completed(futures):
                t, c, rep = futures[future]
                try:
                    r = future.result()
                except Exception as e:
                    print(f"ERROR {c} {t} #{rep}: {type(e).__name__}: {e}", file=sys.stderr)
                    continue
                with lock, open(results, "a") as f:
                    f.write(json.dumps(r) + "\n")
                print(f"{'pass' if r['passed'] else 'FAIL'}  {c:<12} {t:<18} #{rep}  {r['calls']:>3} calls  "
                      f"{r['in'] + r['out']:>9,} tokens  {r['seconds']:>6.0f}s  {r['ended']}"
                      + ("" if r["passed"] else f"  ({r['detail'][:80]})"), file=sys.stderr)
        except KeyboardInterrupt:
            pool.shutdown(cancel_futures=True)
            sys.exit("interrupted: finished runs are saved; run again with the same --name to resume")
    import report
    report.main([str(out)])


if __name__ == "__main__":
    main()
