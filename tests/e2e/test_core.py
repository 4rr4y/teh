"""Startup and settings, the status line and context limit, the shells (each in its own syntax), the system prompt, the
Anthropic format, how commands run, teh-edit and teh-fetch as the model runs them."""
import os
import re

from lib import DEFAULT_SHELL, OS_NAME, SEP, SHELLS, WINDOWS, Suite, family, run_py, section, shutil

s = Suite()
if WINDOWS:
    import ctypes
    # 0 without a console
    CONSOLE_CP = ctypes.windll.kernel32.GetConsoleOutputCP()
s.serve("loop_server.py")
s.serve("auth_server.py", s.w / "auth.log")
s.serve("anthropic_server.py", 8779, s.w / "anth.log")
# Logs every request: the system prompt and the tool
s.serve("caching_server.py", s.w / "req.log")
s.ready()
# A path separator, as a regex
S = re.escape(SEP)

section("startup / settings")
r = s.teh("--help")
s.check("--help shows usage", "TEH_CONTEXT_WINDOW=<n>" in r.both)
r = s.teh("x")
s.check("no settings -> usage, exit 1", r.code == 1 and "usage:" in r.both)
r = s.teh("x", env={"TEH_BASE_URL": "anthropic", "TEH_THINKING": 100})
s.check("TEH_THINKING without TEH_MODEL -> usage, no crash", "usage:" in r.both and "Traceback" not in r.both)
r = s.teh("x", env={"TEH_BASE_URL": "nope", "TEH_MODEL": "m"})
s.check("bad TEH_BASE_URL -> clear error", "not a URL or a known provider" in r.both)
r = s.teh("x", env={"TEH_BASE_URL": "anthropic", "TEH_MODLE": "x"})
s.check("misspelt setting: warning with a suggestion", "unknown setting TEH_MODLE: did you mean TEH_MODEL?" in r.both)
r = s.teh("x", env={"TEH_BASE_URL": "anthropic", "TEH_MODEL": "m", "TEH_MAX_TOKENS": "16k"})
s.check("setting that must be a number", r.both.strip() == "TEH_MAX_TOKENS must be a whole number, not '16k'")
r = s.teh("x", env={"TEH_BASE_URL": "anthropic", "TEH_MODEL": "m", "TEH_SHELL": "nosuch"})
s.check("missing TEH_SHELL -> clear error", "not found; set TEH_SHELL" in r.both)

section("context window + status line")
r = s.teh("go", env={"TEH_BASE_URL": "http://127.0.0.1:8765", "TEH_MODEL": "fake", "TEH_AUTO": 1,
                     "TEH_CONTEXT_WINDOW": 1000000, "TEH_SHELL": DEFAULT_SHELL})
s.check("status line with commas", "in 1,234,567 (1,000,000 cached) · out 4,321 · Σ 1,238,888 (1,000,000 cached) · "
        "ctx 1,238,888/1,000,000 (124%)" in r.err)
s.check("context full: compacts once, then stops if still full (no endless loop)",
        "context window full (1,238,888/1,000,000 tokens): compacting" in r.err and r.err.count("compacted:") == 1
        and "still full right after compacting: stopping" in r.err)
r = s.teh("hi", env={"TEH_BASE_URL": "http://127.0.0.1:8766", "TEH_MODEL": "fake", "TEH_API_KEY": "k1"})
s.check("default context window 262,144", "/262,144" in r.err)
s.check("TEH_API_KEY sent as Bearer", "Bearer k1" in (s.w / "auth.log").read_text())
s.check("stderr has no colour codes when piped", "\x1b" not in r.err)

section("the system prompt, and which shell")
def system_prompt(**env):
    """Return the system prompt and the tool's description that teh sends, with these settings."""
    (s.w / "req.log").write_text("")
    s.teh("go", env={"TEH_BASE_URL": "http://127.0.0.1:8781/v1", "TEH_MODEL": "m", "TEH_AUTO": 1, **env})
    body = s.requests(s.w / "req.log")[0]["body"]
    return body["messages"][0]["content"], body["tools"][0]["function"]["description"]

prompt, _ = system_prompt(TEH_SHELL=DEFAULT_SHELL)
s.check("default role", prompt.startswith("You are a helpful assistant, with shell access"))
s.check("no narration, read selectively", "no preamble or narration" in prompt and "read only what you need" in prompt)
s.check("the scratch folder, by its variable; no input, so non-interactive options",
        "Temporary files (scripts, downloads, notes) go in the folder named by the TEH_SCRATCH environment variable,"
        in prompt and "non-interactive" in prompt)
s.check("teh-fetch and its options, the only way to the web",
        "run `teh-fetch [-H 'Name: value'] [-X METHOD] [-d DATA | --json DATA] URL [word ...]`, the only way" in prompt)
s.check("search, its sources, and that general search engines don't work",
        "Search: `teh-fetch --search SOURCE[:OPTION] QUERY`, SOURCE one of wikipedia, " in prompt
        and "general web search engines don't work" in prompt)
s.check("edit with teh-edit, all of a file's blocks in one call",
        "Edit files with `teh-edit FILE`, given on stdin blocks of: <<<<<<< SEARCH, the exact current lines, =======, "
        "the new lines, >>>>>>> REPLACE; send all of a file's blocks in one call" in prompt)
prompt, _ = system_prompt(TEH_SHELL=DEFAULT_SHELL, TEH_ROLE="a careful sysadmin on a production server")
s.check("TEH_ROLE sets the role", prompt.startswith("You are a careful sysadmin on a production server, with shell"))

for sh in SHELLS:
    prompt, tool = system_prompt(TEH_SHELL=sh)
    s.check(f"{sh}: the system prompt names the system and the shell", f"OS: {OS_NAME}" in prompt
            and f"Shell: {sh}; use its syntax" in prompt)
    s.check(f"{sh}: the tool says which shell runs it", tool == f"Run a {sh} command; returns output and exit code.")
    if family(sh) == "cmd":
        s.check("cmd: chained with &&, no parallel advice (cmd can't wait for jobs), findstr to read",
                "(e.g. with &&)" in prompt and "in parallel" not in prompt and "findstr /n" in prompt)
    elif family(sh) == "powershell":
        s.check(f"{sh}: chained with ;, parallel advice with Start-Job, Select-String to read",
                "(e.g. with ;)" in prompt and "Start-Job" in prompt and "Wait-Job" in prompt
                and "Select-String" in prompt)
    else:
        s.check(f"{sh}: chained with &&, parallel advice with & and wait, rg and sed to read",
                "(e.g. with &&)" in prompt and "& wait" in prompt and "rg -n, sed -n, head" in prompt)

if WINDOWS:
    prompt, _ = system_prompt(PSModulePath=r"C:\Windows\system32\WindowsPowerShell\v1.0\Modules", TEH_SHELL=None)
    s.check("no TEH_SHELL, started from cmd (short PSModulePath): cmd", "Shell: cmd;" in prompt)
    modules = (r"C:\Users\u\Documents\WindowsPowerShell\Modules;C:\Program Files\WindowsPowerShell\Modules;"
               r"C:\Windows\system32\WindowsPowerShell\v1.0\Modules")
    prompt, _ = system_prompt(PSModulePath=modules, TEH_SHELL=None)
    expected = "pwsh" if shutil.which("pwsh") else "powershell"
    s.check(f"no TEH_SHELL, started from PowerShell (its PSModulePath): {expected}", f"Shell: {expected};" in prompt)
else:
    prompt, _ = system_prompt(SHELL="sh", TEH_SHELL=None)
    s.check("no TEH_SHELL: the system's $SHELL is used", "Shell: sh;" in prompt)
    prompt, _ = system_prompt(SHELL="sh", TEH_SHELL="bash")
    s.check("TEH_SHELL wins over $SHELL", "Shell: bash;" in prompt)

# The same scenarios in each shell's own syntax. Each shell gets its own project folder and fake model.
BLOCKS = "<<<<<<< SEARCH\nx = 1\n=======\nx = 10\n>>>>>>> REPLACE\n"
UBLOCKS = "<<<<<<< SEARCH\nnaïve\n=======\nnaïve 中文\n>>>>>>> REPLACE\n"
# Colour codes, a progress bar redrawn with \r, and a line printed 6 times: what tidying output is for
TIDY = ('print("\\x1b[31mred\\x1b[0m")\nprint("load 10%\\rload 100%")\n'
        'for _ in range(6):\n    print("same line, printed again and again")\n')
# The same Python in every shell: double quotes around the code (PowerShell's commands use chr() instead of quotes)
PY_EXIT = '-c "import sys; sys.exit(5)"'
PY_STDERR = '-c "import sys; sys.stderr.write(\'warning\\n\')"'
PY_UTF8 = '-c "print(\'café 中文\')"'
COMMANDS = {
    "cmd": {
        "quote": 'echo it\'s "quoted" & exit /b 3',
        "env": "set TEH_",
        "helpers": "where teh-fetch teh-edit && teh-fetch",
        "stdin": "set /p x=Name? & echo after",
        "order": "echo out1 & echo err1 1>&2 & echo out2",
        "long": "for /l %i in (1,1,20000) do @echo %i",
        # Line 20,000 is 20000
        "saved": 'findstr /n /x 20000 "%TEH_SCRATCH%\\output-1.txt"',
        "edit": "teh-edit f.py < blocks.txt && type f.py",
        "edit_fail": "teh-edit f.py < bad.txt",
        "utf8": "echo café 中文",
        "scratch": 'echo path=%TEH_SCRATCH%& echo note> "%TEH_SCRATCH%\\note.txt" && '
                   'type "%TEH_SCRATCH%\\note.txt"',
        "native_exit": run_py("cmd", PY_EXIT),
        "native_stderr": run_py("cmd", PY_STDERR),
        "py_utf8": run_py("cmd", PY_UTF8),
        "edit_utf8": "teh-edit u.txt < ublocks.txt && type u.txt",
        "helper_mid": "teh-fetch & echo after",
        "tidy": run_py("cmd", "tidy.py"),
        "silent": "ver >nul",
    },
    "powershell": {
        "quote": 'Write-Output "it\'s ""quoted"""; exit 3',
        "env": "Get-ChildItem env:TEH_* | ForEach-Object Name",
        "helpers": "(Get-Command teh-fetch).CommandType; (Get-Command teh-edit).CommandType; teh-fetch",
        "stdin": '$x = Read-Host; "got:[$x]"',
        "order": '"out1"; [Console]::Error.WriteLine("err1"); "out2"',
        "long": "1..20000",
        "saved": "Select-String -Pattern '^20000$' -Path (Get-ChildItem $env:TEH_SCRATCH\\output-*.txt | "
                 "Sort-Object Length)[-1] | ForEach-Object { '{0}:{1}' -f $_.LineNumber, $_.Line }",
        "edit": "@'\n" + BLOCKS + "'@ | teh-edit f.py; Get-Content f.py",
        "edit_fail": "Get-Content bad.txt -Raw | teh-edit f.py",
        "utf8": '"café 中文"',
        "scratch": '"path=$env:TEH_SCRATCH"; "note" | Set-Content $env:TEH_SCRATCH\\note.txt; '
                   "Get-Content $env:TEH_SCRATCH\\note.txt",
        "native_exit": run_py("powershell", "-c 'import sys; sys.exit(5)'"),
        # No " inside: Windows PowerShell drops them from a program's arguments (fixed in PowerShell 7.3)
        "native_stderr": run_py("powershell", "-c 'import sys; sys.stderr.write(chr(119) + chr(97) + chr(114) + "
                                "chr(110) + chr(105) + chr(110) + chr(103) + chr(10))'"),
        "py_utf8": run_py("powershell", "-c 'print(chr(99) + chr(97) + chr(102) + chr(233) + chr(32) + chr(20013) + "
                          "chr(25991))'"),
        "edit_utf8": "@'\n" + UBLOCKS + "'@ | teh-edit u.txt; Get-Content u.txt -Encoding UTF8",
        "helper_mid": 'teh-fetch; "after"',
        "tidy": run_py("powershell", "tidy.py"),
        "silent": "$null = 1",
        "error": 'Get-Content nosuch.txt; "after"',
        "error_last": "Write-Error 'it broke'",
    },
    "posix": {
        "quote": 'echo "it\'s \\"quoted\\""; exit 3',
        "env": "env | grep ^TEH_ | cut -d= -f1",
        "helpers": "command -v teh-fetch; command -v teh-edit; teh-fetch",
        "stdin": 'read x; echo "after got:[$x]"',
        "order": "echo out1; echo err1 >&2; echo out2",
        "long": "seq 1 20000",
        "saved": 'grep -n -x 20000 "$TEH_SCRATCH/output-1.txt"',
        # A heredoc, as the system prompt's advice leads models to write
        "edit": "teh-edit f.py <<'EOF'\n" + BLOCKS + "EOF\ncat f.py",
        "edit_fail": "teh-edit f.py < bad.txt",
        "utf8": 'echo "café 中文"',
        "scratch": 'echo "path=$TEH_SCRATCH"; echo note > "$TEH_SCRATCH/note.txt" && cat "$TEH_SCRATCH/note.txt"',
        "native_exit": run_py("bash", PY_EXIT),
        "native_stderr": run_py("bash", PY_STDERR),
        "py_utf8": run_py("bash", PY_UTF8),
        "edit_utf8": "teh-edit u.txt <<'EOF'\n" + UBLOCKS + "EOF\ncat u.txt",
        "helper_mid": "teh-fetch; echo after",
        "tidy": run_py("bash", "tidy.py"),
        "silent": "true",
    }}
PROJECT_FILES = ["bad.txt", "blocks.txt", "f.py", "tidy.py", "u.txt", "ublocks.txt"]

for n, sh in enumerate(SHELLS):
    section(f"commands in {sh}")
    project = s.w / f"project-{sh}"
    project.mkdir()
    (project / "f.py").write_text("x = 1\ny = 2\n")
    (project / "blocks.txt").write_text(BLOCKS)
    (project / "bad.txt").write_text(BLOCKS.replace("x = 1", "no such line"))
    (project / "u.txt").write_text("naïve\n", encoding="utf-8")
    (project / "ublocks.txt").write_text(UBLOCKS, encoding="utf-8")
    (project / "tidy.py").write_text(TIDY)
    commands = COMMANDS[family(sh)]
    keys = list(commands)
    log = s.script(8800 + n, [commands[k] for k in keys])
    r = s.teh("go", cwd=project, env={"TEH_BASE_URL": f"http://127.0.0.1:{8800 + n}", "TEH_MODEL": "m", "TEH_AUTO": 1,
                                      "TEH_SHELL": sh, "TEH_API_KEY": "sk-SECRET", "TEH_EFFORT": "low"})
    res = {k: s.results(log).get(i + 1, "") for i, k in enumerate(keys)}
    s.check(f"{sh}: the run finishes, every command answered", r.code == 0 and all(res.values()))
    s.check(f"{sh}: quoting intact, and the exit code", 'it\'s "quoted"' in res["quote"] and "[exit 3]" in res["quote"])
    s.check(f"{sh}: commands see TEH_SCRATCH, not the key or other settings",
            "TEH_SCRATCH" in res["env"] and not re.search(r"TEH_(API_KEY|EFFORT|MODEL|BASE_URL|AUTO|SHELL)", res["env"])
            and "sk-SECRET" not in res["env"])
    if family(sh) == "cmd":
        s.check("cmd: teh-fetch and teh-edit are .cmd launchers in the scratch folder",
                re.search(r"\\teh-[^\\]+\\teh-fetch\.cmd", res["helpers"]) and "teh-edit.cmd" in res["helpers"])
    elif family(sh) == "powershell":
        s.check(f"{sh}: teh-fetch and teh-edit are functions (so an & in an address survives)",
                res["helpers"].count("Function") == 2)
        s.check(f"{sh}: errors as plain text, and the command carries on after one",
                "Cannot find path" in res["error"] and "after\n[exit 0]" in res["error"])
        s.check(f"{sh}: an error in the last statement: exit 1", "it broke" in res["error_last"]
                and "[exit 1]" in res["error_last"])
    else:
        s.check(f"{sh}: teh-fetch and teh-edit are found in the scratch folder",
                re.search(r"/teh-[^/]+/teh-fetch\n", res["helpers"]) and re.search(r"/teh-edit\n", res["helpers"]))
    s.check(f"{sh}: the helper runs (its usage), and its exit code comes through",
            "usage: teh.py --fetch" in res["helpers"] and "[exit 1]" in res["helpers"])
    s.check(f"{sh}: no input: a command that asks finishes at once",
            "after" in res["stdin"] or "got:[]" in res["stdin"])
    s.check(f"{sh}: stdout and stderr together, in order",
            re.search(r"out1\s*\n\s*err1\s*\n\s*out2", res["order"]) is not None)
    s.check(f"{sh}: long output: first and last lines, and a note saying how much and where the full output is",
            res["long"].startswith("1\n") and "20000\n[exit 0]" in res["long"]
            and re.search(rf"\[… [\d,]+ characters \([\d,]+ lines\) omitted; full output in \S+{S}teh-[^{S}]+{S}"
                          rf"output-\d+\.txt: use grep or sed -n to read it\]", res["long"]))
    s.check(f"{sh}: a later command can read the saved output", "20000:20000" in res["saved"])
    s.check(f"{sh}: teh-edit applies a block and the file is changed",
            "edited f.py: 1 of 1 blocks applied (at line 1)" in res["edit"] and "x = 10" in res["edit"]
            and (project / "f.py").read_text().startswith("x = 10\n"))
    s.check(f"{sh}: a block that doesn't apply is explained",
            "Not applied, so send only these again" in res["edit_fail"]
            and "SEARCH not found. The closest lines in the file:" in res["edit_fail"])
    s.check(f"{sh}: ... with exit code 1", "[exit 1]" in res["edit_fail"])
    s.check(f"{sh}: teh-edit with non-ASCII text in its blocks and file",
            "1 of 1 blocks applied" in res["edit_utf8"] and "naïve 中文" in res["edit_utf8"]
            and (project / "u.txt").read_text(encoding="utf-8") == "naïve 中文\n")
    s.check(f"{sh}: a program's own exit code", "[exit 5]" in res["native_exit"])
    s.check(f"{sh}: a program writing to stderr, and succeeding: exit 0",
            res["native_stderr"].strip() == "warning\n[exit 0]")
    s.check(f"{sh}: a helper that fails before another statement: the last one's exit code",
            "after" in res["helper_mid"] and "[exit 0]" in res["helper_mid"])
    s.check(f"{sh}: output tidied: no colour codes, a progress bar's final state, repeats counted",
            "red\nload 100%\nsame line, printed again and again\n[… the line above repeated 5 more times]"
            in res["tidy"])
    s.check(f"{sh}: no output at all: only the exit code, without a blank line", res["silent"] == "[exit 0]\n")
    s.check(f"{sh}: the scratch folder: TEH_SCRATCH is set, writable and readable",
            re.search(rf"path=\S+{S}teh-\w+", res["scratch"]) and "note" in res["scratch"].split("path=")[1])
    folder = re.search(r"path=(\S+)", res["scratch"])
    s.check(f"{sh}: the scratch folder is deleted when teh exits", folder and not os.path.exists(folder.group(1)))
    s.check(f"{sh}: nothing was written to the working directory",
            sorted(p.name for p in project.iterdir()) == PROJECT_FILES)
    s.check(f"{sh}: non-ASCII output from the shell comes through", "café 中文" in res["utf8"])
    s.check(f"{sh}: non-ASCII output from Python comes through", "café 中文" in res["py_utf8"])
    if family(sh) == "powershell":
        s.check(f"{sh}: no CLIXML in any output", not any("CLIXML" in v or "<Objs" in v for v in res.values()))

if WINDOWS:
    # teh switches it to UTF-8 while a command runs
    cp = ctypes.windll.kernel32.GetConsoleOutputCP()
    s.check(f"the console's code page is back to what it was ({CONSOLE_CP}) after every run", cp == CONSOLE_CP)

section("timeouts and background jobs (TEH_COMMAND_TIMEOUT=8)")
# Per shell family: a command that runs too long, a background job, and patterns that find each one's process
TIMING = {"cmd": ("echo before & ping -n 31 127.0.0.1 >nul & echo never",
                  'start "" /b ping -n 29 127.0.0.1 >nul & echo started', r"(?i)ping.*-n 31 ", r"(?i)ping.*-n 29 "),
          "powershell": ('"before"; Start-Sleep 31; "never"',
                         "Start-Process ping -ArgumentList '-n','29','127.0.0.1' -WindowStyle Hidden; 'started'",
                         r"(?i)Start-Sleep 31", r"(?i)ping.*-n 29 "),
          "posix": ("echo before; sleep 31; echo never", "sleep 29 & echo started", r"^sleep 31$", r"^sleep 29$")}

for n, sh in enumerate(SHELLS):
    too_long, background, too_long_process, background_process = TIMING[family(sh)]
    log = s.script(8810 + n, [too_long, background])
    r = s.teh("go", env={"TEH_BASE_URL": f"http://127.0.0.1:{8810 + n}", "TEH_MODEL": "m", "TEH_AUTO": 1,
                         "TEH_SHELL": sh, "TEH_COMMAND_TIMEOUT": 8})
    res = s.results(log)
    s.check(f"{sh}: a command that runs too long is stopped, with its output so far",
            "before" in res.get(1, "") and "never" not in res.get(1, "") and "timed out after 8s" in res.get(1, ""))
    s.check(f"{sh}: ... and everything it started is stopped too", not s.processes(too_long_process))
    s.check(f"{sh}: a background job returns at once (the run took {r.seconds:.1f}s, 8s of it the timeout)",
            "started" in res.get(2, "") and "[exit 0]" in res.get(2, "") and r.seconds < 25)
    s.check(f"{sh}: ... and the job is still running", s.processes(background_process))
    s.stop_processes(background_process)

section("TEH_COMMAND_TIMEOUT: 1, and 0 for no limit")
(s.w / "slow.py").write_text("import time\ntime.sleep(3)\nprint('finished')\n")
for timeout, expect in [(1, "stopped, and the message says 1s"), (0, "no limit, the command finishes")]:
    log = s.script(8822, [run_py(DEFAULT_SHELL, "slow.py")])
    s.teh("go", env={"TEH_BASE_URL": "http://127.0.0.1:8822", "TEH_MODEL": "m", "TEH_AUTO": 1,
                     "TEH_SHELL": DEFAULT_SHELL, "TEH_COMMAND_TIMEOUT": timeout})
    result = s.results(log).get(1, "")
    s.check(f"TEH_COMMAND_TIMEOUT={timeout}: {expect}", "timed out after 1s" in result if timeout
            else "finished" in result and "timed out" not in result)

section("the Anthropic format")
r = s.teh("go", env={"TEH_FORMAT": "anthropic", "TEH_BASE_URL": "http://127.0.0.1:8779", "TEH_MODEL": "fake",
                     "TEH_AUTO": 1, "TEH_SHELL": DEFAULT_SHELL})
s.check("tool_use -> tool_result -> answer", "RESULT: hi from anthropic" in r.both and "[exit 0]" in r.both)
s.check("anthropic tool shape + API version", '"input_schema"' in (s.w / "anth.log").read_text()
        and "2026-10-21" in (s.w / "anth.log").read_text())
s.check("cached tokens counted in input", "in 1,005 (1,000 cached)" in r.err)

section("a runaway command, and a command run again")
ENDLESS = '-c "import sys; [sys.stdout.write(chr(121) * 9999 + chr(10)) for _ in iter(int, 1)]"'
BURST = '-c "import sys; sys.stdout.write(chr(121) * 6000000)"'
log = s.script(8820, [run_py(DEFAULT_SHELL, ENDLESS), run_py(DEFAULT_SHELL, BURST)])
r = s.teh("go", env={"TEH_BASE_URL": "http://127.0.0.1:8820", "TEH_MODEL": "m", "TEH_AUTO": 1,
                     "TEH_SHELL": DEFAULT_SHELL, "TEH_COMMAND_TIMEOUT": 0})
res = s.results(log)
s.check(f"endless output, no timeout: stopped at 5,000,000 bytes, quickly ({r.seconds:.1f}s), and the run carries on",
        r.code == 0 and r.seconds < 40 and "[stopped: its output passed 5,000,000 bytes" in res.get(1, ""))
s.check("a fast burst over the cap: cut off, with a note either way",
        re.search(r"\[(stopped: its output passed 5,000,000 bytes|exit 0\] \[output cut off at 5,000,000 bytes)",
                  res.get(2, "")))
# Prints 1 to 200, then (from the second run on) one more line
(s.w / "rerun.py").write_text("import os, pathlib\nprint('\\n'.join(map(str, range(1, 201))))\n"
                              "n = pathlib.Path(os.environ['TEH_SCRATCH'], 'n')\n"
                              "print(n.read_text().strip()) if n.exists() else None\nn.write_text('changed')\n")
command = run_py(DEFAULT_SHELL, "rerun.py")
log = s.script(8821, [command, command, command])
s.teh("go", env={"TEH_BASE_URL": "http://127.0.0.1:8821", "TEH_MODEL": "m", "TEH_AUTO": 1, "TEH_SHELL": DEFAULT_SHELL})
res = s.results(log)
s.check("first run: the whole output", re.search(r"^150$", res.get(1, ""), re.MULTILINE))
s.check("second run: only the changed lines, with a line around them",
        "the lines that changed since the last time this command ran" in res.get(2, "")
        and " 200\n+changed\n[exit 0]" in res.get(2, "") and not re.search(r"^150$", res.get(2, ""), re.MULTILINE))
s.check("third run, identical: one line",
        res.get(3, "") == "[the same output as the last time this command ran]\n[exit 0]\n")

s.finish()
