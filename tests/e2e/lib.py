"""Shared by the end-to-end suites (import it): paths, the shells to test, fake servers, running teh, and a check()
that counts passes and failures. Plain Python, so the suites run the same way on Linux, macOS and Windows.

What differs between systems is kept here, so the suites can say what they check once: which shells there are and
their syntax (family, run_py), how to press Ctrl+C (Suite.ctrl_c), how to run teh without a terminal or console
(Suite.teh(detached=True)) and how to see which processes are still running (Suite.processes).

Tests run against fake API servers on localhost (tests/fakes/), so they need no API key and cost nothing."""
import atexit
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent
H = str(TESTS.parent.parent / "teh.py")  # the harness under test
FAKES = TESTS.parent / "fakes"
PY = sys.executable

WINDOWS = os.name == "nt"
SEP = os.sep
# The system as teh names it in its startup segment and system prompt
OS_NAME = platform.system()
# How the startup segment says to exit chat
EXIT_KEYS = "Ctrl+Z, Enter exits" if WINDOWS else "Ctrl+D exits"
# A path, typed at the chat prompt: a prompt, not a mistyped chat command
PATH_PROMPT = "C:\\Windows\\win.ini" if WINDOWS else "/etc/hosts"

# The shells teh runs the model's commands in. On Windows: cmd, and Windows PowerShell (5.1, on every Windows), and
# PowerShell 7 (pwsh) where it's installed, as on GitHub's runners. Elsewhere: bash and sh, and zsh where it's
# installed.
if WINDOWS:
    SHELLS = ["cmd", "powershell"] + (["pwsh"] if shutil.which("pwsh") else [])
else:
    SHELLS = ["bash", "sh"] + (["zsh"] if shutil.which("zsh") else [])
# The shell for tests that aren't about the shell
DEFAULT_SHELL = SHELLS[0]

def family(shell):
    """Return the syntax a shell uses: "cmd", "powershell" (Windows PowerShell and pwsh) or "posix"."""
    if shell == "cmd":
        return "cmd"
    return "powershell" if shell in ("powershell", "pwsh") else "posix"

def run_py(shell, args):
    """Return a command, in the shell's syntax, that runs this Python with args (which must need no quoting)."""
    return f"& '{PY}' {args}" if family(shell) == "powershell" else f'"{PY}" {args}'

# What teh's own stdout and stderr are encoded in when they're a pipe or a file: UTF-8, whatever the code page and the
# Python version (setup_terminal in teh.py)
ENCODING = "utf-8"

# These fake servers have their port built in; the others take it as their first argument
PORTS = {"loop_server.py": 8765, "auth_server.py": 8766, "echo_server.py": 8767, "slow_server.py": 8768,
         "anthropic_server.py": 8779, "caching_server.py": 8781, "errors_server.py": 8782,
         "compact_server.py": 8786}

def base_env(**extra):
    """Return the environment teh runs in: none of the developer's TEH_ settings, and no $SHELL.

    Without $SHELL, the shell is TEH_SHELL's, so it's the same wherever the tests run (on Windows, Git Bash sets one,
    which teh would pick over cmd and PowerShell). extra: settings to add; None removes a variable.
    """
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("TEH_") and k.upper() != "SHELL"}
    env.update({k: str(v) for k, v in extra.items() if v is not None})
    for k in [k for k, v in extra.items() if v is None]:
        env.pop(k, None)
    return env

class Result:
    """One run of teh: exit code, stdout, stderr (decoded), and how long it took."""
    def __init__(self, code, out, err, seconds):
        self.code, self.out, self.err, self.seconds = code, out, err, seconds
        self.both = out + err

class Suite:
    """One suite's work folder, fake servers and results."""
    def __init__(self):
        # Work folder for logs; removed at the end
        self.w = Path(tempfile.mkdtemp(prefix="tehtest-")).resolve()
        self.servers, self.ports = [], []
        self.passed = self.failed = 0
        # Known problems: shown, but they don't fail the suite (see known)
        self.known_issues = []
        atexit.register(self.cleanup)
        # A neutral working folder: no project AGENTS.md is picked up
        os.chdir(self.w)

    # ----- fake servers
    def serve(self, name, *args):
        """Start a fake server in the background (stopped at the end); return its port."""
        args = [str(a) for a in args]
        port = PORTS.get(name) or int(args[0])
        self.stop_port(port)
        # Something else already answering there would get teh's requests instead, and fail checks obscurely
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            sys.exit(f"port {port} is already in use (a fake server left over from another run?): stop that "
                     "program first")
        except OSError:
            pass
        p = subprocess.Popen([PY, "-B", str(FAKES / name), *args], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        self.servers.append((port, p))
        self.ports.append(port)
        return port

    def stop_port(self, port):
        """Stop a server this suite started on that port (to restart it with other arguments)."""
        for item in [s for s in self.servers if s[0] == port]:
            item[1].kill()
            item[1].wait()
            self.servers.remove(item)
            self.ports.remove(port)

    def ready(self, *ports):
        """Wait until every server started (and these ports) accepts connections, at most 10s."""
        end = time.time() + 10
        for port in [*self.ports, *ports]:
            while time.time() < end:
                try:
                    socket.create_connection(("127.0.0.1", port), 0.2).close()
                    break
                except OSError:
                    time.sleep(0.02)

    def cleanup(self):
        """Stop the servers and remove the work folder."""
        for _, p in self.servers:
            p.kill()
        for _, p in self.servers:
            p.wait()
        os.chdir(Path.home())
        shutil.rmtree(self.w, ignore_errors=True)

    # ----- running teh
    def teh(self, *args, env=None, stdin=b"", cwd=None, timeout=90, detached=False):
        """Run teh once; return a Result.

        env: settings on top of base_env (None removes one). stdin: bytes. detached: without a terminal or console,
        as a scheduled task or a service runs it, so nobody can be asked to approve a command.
        """
        options = {}
        if detached and WINDOWS:
            # No console at all, and stdin not redirected: it's the console's, so there's none
            options, stdin = {"creationflags": subprocess.DETACHED_PROCESS}, None
        elif detached:
            # A new session has no controlling terminal: /dev/tty can't be opened
            options = {"start_new_session": True}
        start = time.monotonic()
        p = subprocess.run([PY, "-B", H, *map(str, args)], env=base_env(**(env or {})), cwd=cwd, input=stdin,
                           capture_output=True, timeout=timeout, **options, check=False)
        return Result(p.returncode, p.stdout.decode(ENCODING, "replace").replace("\r\n", "\n"),
                      p.stderr.decode(ENCODING, "replace").replace("\r\n", "\n"), time.monotonic() - start)

    def ctrl_c(self, seconds, *args, env=None):
        """Run teh, press Ctrl+C after seconds, and return its exit code ("hung" if it didn't exit)."""
        if WINDOWS:
            # Windows has no SIGINT for one process: Ctrl+C goes to every process on a console. So ctrl_c.py runs teh
            # in a (hidden) console of its own, and presses Ctrl+C there
            info = subprocess.STARTUPINFO()
            info.dwFlags, info.wShowWindow = subprocess.STARTF_USESHOWWINDOW, 0  # SW_HIDE
            p = subprocess.run([PY, "-B", str(TESTS / "ctrl_c.py"), str(seconds), H, *args], capture_output=True,
                               text=True, timeout=60, env=base_env(**(env or {})),
                               creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=info, check=False)
            return p.stdout.strip() or p.stderr.strip()[-200:]
        p = subprocess.Popen([PY, "-B", H, *args], env=base_env(**(env or {})), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(seconds)
        p.send_signal(signal.SIGINT)
        try:
            return p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
            return "hung"

    def pty(self, *inputs, cwd=None, **env):
        """Unix only: run teh's chat in a pseudo-terminal, typing these inputs at its prompts; return all it showed."""
        p = subprocess.run([PY, "-B", str(TESTS / "pty_run.py"), H, *inputs], capture_output=True, timeout=60,
                           cwd=cwd, env=base_env(**{"TEH_MODEL": "fake", "TEH_SHELL": DEFAULT_SHELL, **env}),
                           check=False)
        return p.stdout.decode(ENCODING, "replace")

    def script(self, port, commands, log=None):
        """Start a script_server that has teh run these commands; return its log's path."""
        log = log or self.w / f"results-{port}.log"
        cmds = self.w / f"cmds-{port}.txt"
        cmds.write_text("\n---\n".join(commands), encoding="utf-8")
        log.write_text("", encoding="utf-8")
        self.serve("script_server.py", port, cmds, log)
        self.ready()
        return log

    def results(self, log):
        """Return the command results a script_server logged: {number: the result}."""
        text = Path(log).read_text(encoding="utf-8", errors="replace")
        parts = text.split("=== result ")[1:]
        return {int(p.split(":", 1)[0]): p.split(":\n", 1)[1] if ":\n" in p else "" for p in parts}

    def requests(self, log):
        """Return the JSON lines a fake server logged."""
        return [json.loads(line) for line in Path(log).read_text(encoding="utf-8").splitlines() if line.strip()]

    # ----- processes
    def processes(self, pattern):
        """Return the command lines of running processes that match the regex pattern."""
        if WINDOWS:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ("Get-CimInstance Win32_Process | "
                                  "ForEach-Object CommandLine")], capture_output=True, text=True, check=False).stdout
        else:
            out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True, check=False).stdout
            # Without the process id in front
            out = "\n".join(line.strip().split(" ", 1)[-1] for line in out.splitlines())
        return [line for line in out.splitlines() if re.search(pattern, line)]

    def stop_processes(self, pattern):
        """Stop the running processes whose command lines match the regex pattern (to tidy up after a test)."""
        if WINDOWS:
            subprocess.run(["powershell", "-NoProfile", "-Command", ("Get-CimInstance Win32_Process | Where-Object "
                            f"{{ $_.CommandLine -match '{pattern}' }} | ForEach-Object "
                            "{ Stop-Process -Id $_.ProcessId -Force }")], capture_output=True, check=False)
        else:
            subprocess.run(["pkill", "-f", pattern], capture_output=True, check=False)

    # ----- results
    def check(self, description, condition):
        """Record a check: condition is a value, or a function that returns one (an exception fails it)."""
        try:
            ok = bool(condition() if callable(condition) else condition)
        # Any error in a check fails that check, with why, and the suite goes on
        except Exception as e:  # noqa: BLE001
            ok, description = False, f"{description} ({type(e).__name__}: {e})"
        if ok:
            self.passed += 1
            print(f"PASS  {description}", flush=True)
        else:
            self.failed += 1
            print(f"FAIL  {description}", flush=True)
        return ok

    def known(self, description, condition, issue):
        """Record a known problem in teh, not in the test: checked like check(), but a failure is reported as KNOWN,
        with the issue, and doesn't fail the suite. If it passes, the problem is fixed: it says so, so the marker can
        become a check()."""
        try:
            ok = bool(condition() if callable(condition) else condition)
        # As in check(): any error means the problem is still there
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            self.passed += 1
            print(f"PASS  {description} (was a known problem: now fixed, make it a check())", flush=True)
        else:
            self.known_issues.append(description)
            print(f"KNOWN {description}\n      ({issue})", flush=True)

    def finish(self):
        """Print the totals, and exit with 1 if any check failed."""
        known = f"   known: {len(self.known_issues)}" if self.known_issues else ""
        print(f"\npassed: {self.passed}   failed: {self.failed}{known}")
        sys.exit(1 if self.failed else 0)

def section(title):
    """Print a section heading."""
    print(f"== {title}", flush=True)
