"""Shared by the Windows test suites (import it): paths, fake servers, running teh, and a check() that counts passes and
failures. The Windows counterpart of tests/unix/lib.sh, in Python, so the suites need nothing but Python itself.

Tests run against fake API servers on localhost (tests/fakes/, shared), so they need no API key and cost nothing."""
import atexit, json, os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path

TESTS = Path(__file__).resolve().parent
H = str(TESTS.parent.parent / "teh.py")  # the harness under test
FAKES = TESTS.parent / "fakes"           # shared with other systems' tests
PY = sys.executable

# The shells teh runs the model's commands in on Windows. Windows PowerShell (5.1) is on every Windows; PowerShell 7
# (pwsh) only where it's installed, as on GitHub's runners.
SHELLS = ["cmd", "powershell"] + (["pwsh"] if shutil.which("pwsh") else [])

# What teh's own stdout and stderr are encoded in when they're a pipe or a file: UTF-8, whatever the code page and the
# Python version (setup_terminal in teh.py)
ENCODING = "utf-8"

PORTS = {"loop_server.py": 8765, "auth_server.py": 8766, "echo_server.py": 8767, "slow_server.py": 8768,
         "anthropic_server.py": 8779, "caching_server.py": 8781, "errors_server.py": 8782,
         "compact_server.py": 8786}  # these have their port built in; the others take it as their first argument

def base_env(**extra):  # the environment teh runs in: none of the developer's TEH_ settings, no Unix $SHELL (Git Bash
    env = {k: v for k, v in os.environ.items()            # sets one, which teh would pick over cmd and PowerShell)
           if not k.upper().startswith("TEH_") and k.upper() != "SHELL"}
    env.update({k: str(v) for k, v in extra.items() if v is not None})
    for k in [k for k, v in extra.items() if v is None]:  # None: remove the variable
        env.pop(k, None)
    return env

class Result:  # one run of teh: exit code, stdout, stderr (decoded), and how long it took
    def __init__(self, code, out, err, seconds):
        self.code, self.out, self.err, self.seconds = code, out, err, seconds
        self.both = out + err

class Suite:
    def __init__(self):
        self.w = Path(tempfile.mkdtemp(prefix="tehtest-")).resolve()  # work folder for logs; removed at the end
        self.servers, self.ports = [], []
        self.passed = self.failed = 0
        self.known_issues = []  # known problems: shown, but they don't fail the suite (see known())
        atexit.register(self.cleanup)
        os.chdir(self.w)  # a neutral working folder: no project AGENTS.md is picked up

    # ----- fake servers
    def serve(self, name, *args):  # start a fake server in the background, stopped at the end
        args = [str(a) for a in args]
        port = PORTS.get(name) or int(args[0])
        self.stop_port(port)
        try:  # something else already answering there would get teh's requests instead, and fail checks obscurely
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            sys.exit(f"port {port} is already in use (a fake server left over from another run?): stop that "
                     f"program first, e.g. find it with: netstat -ano | findstr :{port}")
        except OSError:
            pass  # free
        p = subprocess.Popen([PY, "-B", str(FAKES / name), *args], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        self.servers.append((port, p))
        self.ports.append(port)
        return port

    def stop_port(self, port):  # stop a server this suite started on that port (to restart it with other arguments)
        for item in [s for s in self.servers if s[0] == port]:
            item[1].kill()
            item[1].wait()
            self.servers.remove(item)
            self.ports.remove(port)

    def ready(self, *ports):  # wait until every server started (and these ports) accepts connections, at most 10s
        end = time.time() + 10
        for port in [*self.ports, *ports]:
            while time.time() < end:
                try:
                    socket.create_connection(("127.0.0.1", port), 0.2).close()
                    break
                except OSError:
                    time.sleep(0.02)

    def cleanup(self):
        for _, p in self.servers:
            p.kill()
        for _, p in self.servers:
            p.wait()
        os.chdir(Path.home())
        shutil.rmtree(self.w, ignore_errors=True)

    # ----- running teh
    def teh(self, *args, env=None, stdin=b"", cwd=None, timeout=90, flags=0):
        """Run teh once -> Result. env: settings on top of base_env (None removes one); stdin: bytes, or None for no
        redirection at all; flags: Windows creation flags, e.g. subprocess.DETACHED_PROCESS for no console."""
        start = time.monotonic()
        p = subprocess.run([PY, "-B", H, *map(str, args)], env=base_env(**(env or {})), cwd=cwd,
                           input=stdin if stdin is not None else None,
                           stdin=subprocess.DEVNULL if stdin is None else None,
                           capture_output=True, timeout=timeout, creationflags=flags)
        return Result(p.returncode, p.stdout.decode(ENCODING, "replace").replace("\r\n", "\n"),
                      p.stderr.decode(ENCODING, "replace").replace("\r\n", "\n"), time.monotonic() - start)

    def script(self, port, commands, log=None):  # a script_server that has teh run these commands -> its log's path
        log = log or self.w / f"results-{port}.log"
        cmds = self.w / f"cmds-{port}.txt"
        cmds.write_text("\n---\n".join(commands), encoding="utf-8")
        log.write_text("", encoding="utf-8")
        self.serve("script_server.py", port, cmds, log)
        self.ready()
        return log

    def results(self, log):  # the command results a script_server logged -> {number: the result}
        text = Path(log).read_text(encoding="utf-8", errors="replace")
        parts = text.split("=== result ")[1:]
        return {int(p.split(":", 1)[0]): p.split(":\n", 1)[1] if ":\n" in p else "" for p in parts}

    def requests(self, log):  # the JSON lines a fake server logged
        return [json.loads(line) for line in Path(log).read_text(encoding="utf-8").splitlines() if line.strip()]

    # ----- results
    def check(self, description, condition):
        try:
            ok = bool(condition() if callable(condition) else condition)
        except Exception as e:  # a check that raises fails, with why
            ok, description = False, f"{description} ({type(e).__name__}: {e})"
        if ok:
            self.passed += 1
            print(f"PASS  {description}")
        else:
            self.failed += 1
            print(f"FAIL  {description}")
        return ok

    def known(self, description, condition, issue):
        """A known problem in teh, not in the test: checked like check(), but a failure is reported as KNOWN, with the
        issue, and doesn't fail the suite. If it passes, the problem is fixed: say so, so the marker gets removed."""
        try:
            ok = bool(condition() if callable(condition) else condition)
        except Exception:
            ok = False
        if ok:
            self.passed += 1
            print(f"PASS  {description} (was a known problem: now fixed, make it a check())")
        else:
            self.known_issues.append(description)
            print(f"KNOWN {description}\n      ({issue})")

    def finish(self):
        print(f"\npassed: {self.passed}   failed: {self.failed}" + (f"   known: {len(self.known_issues)}" if self.known_issues else ""))
        sys.exit(1 if self.failed else 0)

def section(title):
    print(f"== {title}", flush=True)
