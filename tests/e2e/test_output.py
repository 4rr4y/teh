"""One-shot results for scripts: exit codes for each way a run can end, TEH_OUTPUT=json, piped input (and non-English
text through pipes), and running without a terminal or console. Chat input is in test_chat.py."""
import json
import subprocess

from lib import DEFAULT_SHELL, PY, SHELLS, WINDOWS, H, Suite, base_env, family, section

s = Suite()
# 8766: answers "ok"
s.serve("auth_server.py", s.w / "auth.log")
# 8765: always calls a tool, reports huge usage
s.serve("loop_server.py")
# 8782: /cut/, /400/
s.serve("errors_server.py")
# 8768: answers after 3.5s
s.serve("slow_server.py")
s.serve("refusal_server.py", 8774, s.w / "refusal.log", "refusal")
# 8781: logs request bodies
s.serve("caching_server.py", s.w / "req.log")
s.script(8771, ["echo one", "exit 7"], s.w / "cmds.log")
s.ready()

def oneshot(stdin=b"", **env):
    """Run teh once with the task "go"; return the Result."""
    return s.teh("go", stdin=stdin, env={"TEH_SHELL": DEFAULT_SHELL, **env})

section("exit codes")
s.check("done -> 0", oneshot(TEH_BASE_URL="http://127.0.0.1:8766", TEH_MODEL="m").code == 0)
s.check("error (HTTP 400) -> 1", oneshot(TEH_BASE_URL="http://127.0.0.1:8782/400", TEH_MODEL="m").code == 1)
s.check("refused -> 2", oneshot(TEH_BASE_URL="http://127.0.0.1:8774", TEH_MODEL="m").code == 2)
s.check("context window full -> 3", oneshot(TEH_BASE_URL="http://127.0.0.1:8765", TEH_MODEL="m", TEH_AUTO=1,
                                            TEH_CONTEXT_WINDOW=1000).code == 3)
s.check("reply cut off -> 4", oneshot(TEH_BASE_URL="http://127.0.0.1:8782/cut", TEH_MODEL="m").code == 4)
s.check("no budget by default: a run of 3 model calls finishes",
        oneshot(TEH_BASE_URL="http://127.0.0.1:8771", TEH_MODEL="m", TEH_AUTO=1).code == 0)
r = oneshot(TEH_BASE_URL="http://127.0.0.1:8771", TEH_MODEL="m", TEH_AUTO=1, TEH_TURN_BUDGET=1)
s.check("turn budget reached -> 5, before the call that would pass it, with calls on the status line", r.code == 5
        and r.err.count("\n$ ") == 1 and "(0%) · 1/1 calls" in r.err
        and "turn budget reached: 1 model calls for this prompt (TEH_TURN_BUDGET=1)" in r.err)
s.check("a turn budget the run fits in: no effect",
        oneshot(TEH_BASE_URL="http://127.0.0.1:8771", TEH_MODEL="m", TEH_AUTO=1, TEH_TURN_BUDGET=3).code == 0)
r = oneshot(TEH_BASE_URL="http://127.0.0.1:8765", TEH_MODEL="m", TEH_AUTO=1, TEH_CONTEXT_WINDOW=100000000,
            TEH_TOKEN_BUDGET=2000000)
s.check("token budget reached -> 5, with the budget on the status line", r.code == 5
        and r.err.count("· fake ·") == 1 and "Σ 1,238,888 (1,000,000 cached | 2,000,000 budget) · ctx" in r.err
        and "token budget reached: 1,238,888 tokens used, and the next call would need about 1,238," in r.err
        and " more (TEH_TOKEN_BUDGET=2,000,000, for the whole run)" in r.err)
code = s.ctrl_c(1.5, "go", env={"TEH_BASE_URL": "http://127.0.0.1:8768", "TEH_MODEL": "m"})
s.check(f"cancelled (Ctrl+C) -> 130 (got {code})", str(code) == "130")

section("no terminal or console")
# Started without one (as by cron, a scheduled task or a service), with no TEH_AUTO: nobody can approve a command
r = s.teh("go", detached=True, env={"TEH_BASE_URL": "http://127.0.0.1:8771", "TEH_MODEL": "m",
                                    "TEH_SHELL": DEFAULT_SHELL})
s.check("no terminal and no TEH_AUTO: a clear error, exit 1", r.code == 1
        and "no terminal to approve commands: set TEH_AUTO=1" in r.err)
r = s.teh("go", detached=True, env={"TEH_BASE_URL": "http://127.0.0.1:8771", "TEH_MODEL": "m",
                                    "TEH_SHELL": DEFAULT_SHELL, "TEH_AUTO": 1})
s.check("no terminal, with TEH_AUTO=1: the commands run, exit 0", r.code == 0 and "\n$ exit 7\n" in r.err)

section("TEH_OUTPUT=json")
r = oneshot(TEH_BASE_URL="http://127.0.0.1:8771", TEH_MODEL="m", TEH_AUTO=1, TEH_OUTPUT="json")
d = json.loads(r.out) if r.out.strip().startswith("{") else {}
s.check("stdout is exactly one JSON object: the answer isn't also printed as text", r.out.count("\n") == 1 and d)
s.check("ended done, answer, model, no error", (d.get("ended"), d.get("answer"), d.get("model"), d.get("error"))
        == ("done", "done", "m", None))
s.check("commands with their exit codes",
        d.get("commands") == [{"command": "echo one", "exit": 0}, {"command": "exit 7", "exit": 7}])
s.check("token totals", d.get("tokens") == {"input": 30, "cached": 0, "output": 3, "context": 11})
s.check("status still on stderr", "· fake · default" in r.err)
r = oneshot(TEH_BASE_URL="http://127.0.0.1:8774", TEH_MODEL="m", TEH_OUTPUT="json")
d = json.loads(r.out)
s.check("refusal: ended refused, with the reason", d["ended"] == "refused" and "help with that" in d["error"])
r = oneshot(TEH_BASE_URL="http://127.0.0.1:8771", TEH_MODEL="m", TEH_AUTO=1, TEH_TURN_BUDGET=1, TEH_OUTPUT="json")
d = json.loads(r.out)
s.check("budget: ended budget, with why, and the commands that ran",
        (d["ended"], len(d["commands"]), "turn budget" in d["error"]) == ("budget", 1, True))

section("piped input")
(s.w / "req.log").write_text("")
r = oneshot(stdin="a log line\r\n\x1b[31mred\x1b[0m café\r\n".encode(),
            TEH_BASE_URL="http://127.0.0.1:8781/v1", TEH_MODEL="m", TEH_AUTO=1)
prompt = s.requests(s.w / "req.log")[0]["body"]["messages"][1]["content"]
s.check("piped input joins the task, tidied (no colour codes, no \\r), UTF-8 kept",
        r.code == 0 and prompt == "go\n\na log line\nred café")
r = s.teh(stdin=b"only piped", env={"TEH_BASE_URL": "http://127.0.0.1:8766", "TEH_MODEL": "m"})
s.check("piped input alone is a one-shot task; the answer goes to stdout", r.code == 0 and r.out.strip() == "ok")

section("non-English text through pipes")
s.serve("prompt_server.py", 8793)
s.ready()
answer_env = base_env(TEH_BASE_URL="http://127.0.0.1:8793", TEH_MODEL="m")
(s.w / "in.txt").write_bytes("diff café 中文\n".encode())
r = s.teh("review", stdin=(s.w / "in.txt").read_bytes(),
          env={"TEH_BASE_URL": "http://127.0.0.1:8793", "TEH_MODEL": "m"})
s.check("piped UTF-8 arrives whole, and the answer comes out as UTF-8",
        r.out.strip() == "got: review |  | diff café 中文")
# The shell's own pipeline: a file piped in, the answer redirected to a file
if WINDOWS:
    # A command line, not a list: cmd parses its own, quotes and all
    pipeline, name = f'cmd /d /s /c "type in.txt | "{PY}" -B "{H}" review > answer.txt"', "cmd: type file | teh > file"
else:
    pipeline, name = ["sh", "-c", f'cat in.txt | "{PY}" -B "{H}" review > answer.txt'], "sh: cat file | teh > file"
subprocess.run(pipeline, cwd=s.w, timeout=60, capture_output=True, env=answer_env, check=False)
s.check(name, (s.w / "answer.txt").read_text(encoding="utf-8").strip() == "got: review |  | diff café 中文")

if WINDOWS:
    r = s.teh("review", stdin="diff café\n".encode("cp1252"), env={"TEH_BASE_URL": "http://127.0.0.1:8793",
                                                                        "TEH_MODEL": "m"})
    s.check("piped text in the ANSI code page (an older program's) is read as such",
            r.out.strip() == "got: review |  | diff café")
    # The README's profile lines, as they'd be in a profile. The function passes on piped input only when there is
    # some, so a teh started without any still gets the console (chat, approvals). Every line works in PowerShell 1.0
    PROFILE = ("$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false\n"
               "function teh { $in = @($input); "
               'if ($in.Count) { $in | python "TEH" $args } else { python "TEH" $args } }\n'
               ).replace('python "TEH"', f'& "{PY}" "{H}"')
    for sh in [x for x in SHELLS if family(x) == "powershell"]:
        (s.w / "answer.txt").unlink(missing_ok=True)
        # The answer in a variable: then teh's output is a pipe, not the console
        script = PROFILE + ("$a = Get-Content -Encoding UTF8 in.txt | teh review\n"
                            "[System.IO.File]::WriteAllText((Join-Path (Get-Location) 'answer.txt'), \"$a\")\n"
                            "$b = teh 'no input here'\n"
                            "[System.IO.File]::AppendAllText((Join-Path (Get-Location) 'answer.txt'), "
                            "\"`n$b`n$LASTEXITCODE\")")
        p = subprocess.run([sh, "-NoProfile", "-NonInteractive", "-Command", script], cwd=s.w, timeout=60,
                           capture_output=True, env=answer_env, check=False)
        saved = s.w / "answer.txt"
        answer = saved.read_text(encoding="utf-8") if saved.exists() else p.stderr.decode()
        s.check(f"{sh}: Get-Content file | teh: the input arrives, and the answer comes back, non-English text whole",
                answer.splitlines()[:1] == ["got: review |  | diff café 中文"])
        s.check(f"{sh}: teh with nothing piped: no input added, exit code 0",
                answer.splitlines()[1:] == ["got: no input here", "0"])

s.finish()
