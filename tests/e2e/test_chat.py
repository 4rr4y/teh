"""Interactive behaviour: approvals, refusals, chat commands, the startup segment, chat input (pastes, typed lines, a \\
at the end of a line), the caching startup line and /clear, /compact, AGENTS.md and the scratch folder.

Chat runs through chat_run.py, which works on every system. On Unix, what needs a real terminal runs in a pseudo-
terminal too: Ctrl+C during a command, the live thinking timer, the terminal's paste markers, colour, and signals."""
import glob
import os
import subprocess
import tempfile

from lib import (
    DEFAULT_SHELL,
    ENCODING,
    EXIT_KEYS,
    OS_NAME,
    PATH_PROMPT,
    PY,
    SEP,
    SHELLS,
    TESTS,
    WINDOWS,
    H,
    Suite,
    base_env,
    section,
)

s = Suite()
# 8766: answers "ok"
s.serve("auth_server.py", s.w / "auth.log")
# 8781: logs requests; a tool call (echo hi), then "done"
s.serve("caching_server.py", s.w / "req.log")
s.serve("compact_server.py", s.w / "compact.log")
# 8768: answers after 3.5s
s.serve("slow_server.py")
# Each refusal server refuses only the first request it gets, so each test has its own
s.serve("refusal_server.py", 8776, s.w / "roles.log", "anthropic")
s.serve("refusal_server.py", 8773, s.w / "r1.log", "anthropic")
s.serve("refusal_server.py", 8774, s.w / "r2.log", "refusal")
s.serve("refusal_server.py", 8775, s.w / "r3.log", "filter")
s.script(8771, [f"echo {word}" for word in ("one", "two", "three", "four", "five", "six")], s.w / "approvals.log")
s.ready()
scratch_before = set(glob.glob(os.path.join(tempfile.gettempdir(), "teh-*")))

def chat(*inputs, cwd=None, **env):
    """Run a chat with these inputs; return everything it showed (stdout and stderr), inputs marked <<'input'>>."""
    # One stream, so the inputs are in their place among the output
    p = subprocess.run([PY, "-B", str(TESTS / "chat_run.py"), *inputs], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=120, cwd=cwd,
                       env=base_env(PYTHONUNBUFFERED=1, **{"TEH_MODEL": "fake", "TEH_SHELL": DEFAULT_SHELL, **env}),
                       check=False)
    return p.stdout.decode(ENCODING, "replace").replace("\r\n", "\n")

section("approvals")
out = chat("go", "", "n", "use another command instead", "y", "a", TEH_BASE_URL="http://127.0.0.1:8771")
res = s.results(s.w / "approvals.log")
s.check("Enter and n decline; other text declines and is passed on",
        res.get(1, "").strip() == "User declined." and res.get(2, "").strip() == "User declined."
        and res.get(3, "").strip() == "User declined: use another command instead")
s.check("y runs the command", res.get(4, "").strip() == "four\n[exit 0]")
s.check("a runs it and every later one, without asking again", out.count("instead: ") == 5
        and "five" in res.get(5, "") and "six" in res.get(6, ""))

section("refusals")
out = chat("hi", "again", TEH_BASE_URL="http://127.0.0.1:8776", TEH_FORMAT="anthropic")
s.check("anthropic refusal message",
        "[refused] [the model declined to respond: cyber · This looks like malware development.]" in out)
s.check("after a refusal the next prompt starts clean", (s.w / "roles.log").read_text().splitlines()[1]
        == "request 2 roles: ['user']")
r = s.teh("hi", env={"TEH_BASE_URL": "http://127.0.0.1:8773", "TEH_MODEL": "fake", "TEH_FORMAT": "anthropic"})
s.check("one-shot: anthropic refusal message", "[refused] [the model declined to respond: cyber · " in r.err)
r = s.teh("hi", env={"TEH_BASE_URL": "http://127.0.0.1:8774", "TEH_MODEL": "fake"})
s.check("openai refusal field", "declined to respond: I can't help with that." in r.err)
r = s.teh("hi", env={"TEH_BASE_URL": "http://127.0.0.1:8775", "TEH_MODEL": "fake"})
s.check("content filter", "blocked by the provider's content filter" in r.err)

section("the startup segment, per shell")
for sh in SHELLS:
    out = chat(TEH_BASE_URL="http://127.0.0.1:8766", TEH_SHELL=sh)
    s.check(f"{sh}: startup segment: the system, the shell, scratch folder, role, exit keys",
            "teh · startup" in out and f"  os       {OS_NAME}" in out and f"  shell    {sh} (" in out
            and "scratch  " in out and f"{SEP}teh-" in out and "agents   none found" in out
            and "role     a helpful assistant" in out and f"keys     Ctrl+C cancels the current turn · {EXIT_KEYS}"
            in out)

section("chat commands")
out = chat("/effort low", "/help", "hi", "/clear", "/compact", "/hlep", PATH_PROMPT,
           TEH_BASE_URL="http://127.0.0.1:8766")
s.check("/effort: the status line, with the effort, and no other confirmation",
        "· fake · low · Σ 0 · ctx 0/262,144 (0%)" in out and "effort: low" not in out)
s.check("/help lists the commands", "commands:  /budget [tokens N | calls N | off]" in out)
s.check("prompt answered; effort shown in status", "\nok\n" in out and "· fake · low · 0." in out)
s.check("/clear: the status line, no other confirmation", "conversation cleared" not in out)
s.check("/compact with nothing to compact says so", "nothing to compact: the conversation is empty" in out)
s.check("mistyped command: not sent to the model; a path is a prompt",
        "unknown command /hlep: /help lists them" in out and out.count("· fake · low · 0.") == 2)
out = chat("/budget", "/budget calls 5", "/budget tokens 2m", "/budget off", "hi", "/undo", "/undo",
           TEH_BASE_URL="http://127.0.0.1:8766", TEH_TOKEN_BUDGET=900000)
s.check("/budget changes the budgets, shown on the status line; rejects what isn't a whole number",
        "Σ 0 (900,000 budget) · ctx 0/262,144 (0%)" in out
        and "Σ 0 (900,000 budget) · ctx 0/262,144 (0%) · 0/5 calls" in out and "usage: /budget" in out
        and "budget: " not in out)
s.check("/undo removes the last prompt (the context goes back to 0), then there's nothing left to undo",
        "· fake · default · Σ " in out.split("<<'/undo'>>")[1] and "ctx 0/262,144 (0%)" in out.split("<<'/undo'>>")[1]
        and "nothing to undo" in out.split("<<'/undo'>>")[2])

section("chat input")
def first_prompts(*inputs, terminal=False):
    """Run a chat with these inputs (typed in a pseudo-terminal if terminal); return the user prompts teh sent."""
    (s.w / "req.log").write_text("")
    env = {"TEH_BASE_URL": "http://127.0.0.1:8781/v1", "TEH_AUTO": 1}
    s.pty(*inputs, "\\x04", **env) if terminal else chat(*inputs, **env)
    reqs = s.requests(s.w / "req.log")
    return [m["content"] for r in reqs for m in r["body"]["messages"] if m["role"] == "user"]

s.check("lines pasted at once -> one prompt",
        first_prompts("first line\\nsecond line\\nthird line")[0] == "first line\nsecond line\nthird line")
s.check("a line ending in \\ continues on the next", first_prompts("one \\\\", "two")[0] == "one \ntwo")
prompts = first_prompts("typed one", "typed two")
s.check("lines typed separately -> separate prompts", prompts[0] == "typed one" and "typed two" in prompts)
if not WINDOWS:
    s.check("terminal: lines pasted at once (no paste markers) -> one prompt",
            first_prompts("first line\\nsecond line\\nthird line\\n", terminal=True)[0]
            == "first line\nsecond line\nthird line")
    s.check("terminal: bracketed paste (the terminal's paste markers) -> one prompt",
            first_prompts("\\x1b[200~alpha\\nbeta\\x1b[201~\\r", terminal=True)[0] == "alpha\nbeta")
    s.check("terminal: a line ending in \\ continues on the next",
            first_prompts("one \\\\\\n", "two\\n", terminal=True)[0] == "one \ntwo")
    prompts = first_prompts("typed one\\n", "typed two\\n", terminal=True)
    s.check("terminal: lines typed separately -> separate prompts",
            prompts[0] == "typed one" and "typed two" in prompts)

section("caching: the startup line and /clear")
U = "http://127.0.0.1:8781"
s.check("anthropic long: cache_control marker (1h)", "cache    cache_control marker (1h)" in chat(
    TEH_BASE_URL=f"{U}/api.anthropic.com/v1", TEH_MODEL="claude-x", TEH_CACHE_RETENTION="long"))
s.check("openai long: session id + retention", "cache    session id in prompt_cache_key · long retention "
        "(prompt_cache_retention=24h)" in chat(TEH_BASE_URL=f"{U}/api.openai.com/v1", TEH_MODEL="gpt",
                                                TEH_CACHE_RETENTION="long"))
s.check("unlisted: provider default", "cache    provider default (automatic, if any)" in chat(
    TEH_BASE_URL=f"{U}/api.groq.com/openai/v1"))
(s.w / "req.log").write_text("")
chat("one", "/clear", "two", TEH_BASE_URL=f"{U}/api.x.ai/v1", TEH_AUTO=1)
reqs = s.requests(s.w / "req.log")
s.check("/clear gives a new session id", len(reqs) == 4
        and len({{k.lower(): v for k, v in r["headers"].items()}["x-grok-conv-id"] for r in reqs}) == 2)

section("/compact in chat")
(s.w / "compact.log").write_text("")
chat("first task", "/compact keep the db details", "second task", TEH_BASE_URL="http://127.0.0.1:8786/v1",
     TEH_AUTO=1)
reqs = [line["body"] for line in s.requests(s.w / "compact.log") if "body" in line]
s.check("the summary request carries the focus text",
        "Also keep: keep the db details" in reqs[2]["messages"][-1]["content"])
s.check("the next prompt follows the summary", [m["content"][:20] for m in reqs[3]["messages"][1:]]
        == ["[This conversation w", "second task"])

section("AGENTS.md")
repo = s.w / "b" / "repo"
(repo / ".git").mkdir(parents=True)
(repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
(repo / "AGENTS.md").write_text("RULE-1")
(repo / "sub").mkdir()
(s.w / "b" / "AGENTS.md").write_text("ABOVE")
plain = s.w / "plain"
(plain / "sub").mkdir(parents=True)
(plain / "AGENTS.md").write_text("no project here")
ok = {"TEH_BASE_URL": "http://127.0.0.1:8766", "TEH_MODEL": "fake"}
r = s.teh("hi", cwd=repo, env=ok)
s.check("AGENTS.md in the working directory: loaded, one line on stderr", f"· using {repo}{SEP}AGENTS.md (6 characters"
        in r.err)
r = s.teh("hi", cwd=repo / "sub", env=ok)
s.check("from a subfolder: the project root's AGENTS.md (the folder with .git), nothing above the root",
        f"· using {repo}{SEP}AGENTS.md (6 characters" in r.err and str(s.w / "b" / "AGENTS.md") not in r.err)
r = s.teh("hi", cwd=plain / "sub", env=ok)
s.check("no project root (.git, .hg, .jj): only the working directory's, not its parent's", "using" not in r.err)
r = s.teh("hi", cwd=repo, env=dict(ok, TEH_AGENTS_MD=0))
s.check("TEH_AGENTS_MD=0 turns it off", "using" not in r.err)
out = chat(cwd=repo, TEH_BASE_URL="http://127.0.0.1:8766")
s.check("chat: the agents line names it, and a small one gets no warning",
        f"agents   {repo}{SEP}AGENTS.md (6 characters, added" in out and "! AGENTS.md" not in out)
big = s.w / "big"
big.mkdir()
big_text = "\n".join(f"rule {i}: " + "keep the code tidy " * 3 for i in range(600)) + "\nLAST_RULE"
(big / "AGENTS.md").write_text(big_text)
# Logs the system prompt
s.serve("echo_server.py", "echo hi", s.w / "agsys.log")
s.ready()
r = s.teh("hi", cwd=big, env={"TEH_BASE_URL": "http://127.0.0.1:8767", "TEH_MODEL": "fake", "TEH_AUTO": 1,
                              "TEH_SHELL": DEFAULT_SHELL})
s.check("AGENTS.md over the limit, one-shot: the usual stderr line says it was cut",
        f"· using {big}{SEP}AGENTS.md (" in r.err
        and " characters, over the 32,768 limit: only the first " in r.err and " were added to the system prompt)"
        in r.err)
system = (s.w / "agsys.log").read_text(encoding="utf-8")
cut_note = f"\n[… AGENTS.md is cut here: it has {len(big_text):,} characters."
s.check("the model gets its start, cut at a line break, and where to read the rest",
        "\nrule 0: " in system and "LAST_RULE" not in system and cut_note in system
        and f"Read the rest from {big}{SEP}AGENTS.md when it's relevant]" in system
        and system.split(cut_note)[0].endswith("tidy "))
out = chat(cwd=big, TEH_BASE_URL="http://127.0.0.1:8766")
s.check("AGENTS.md over the limit, chat: a warning after the startup segment",
        "keys     " in out and "! AGENTS.md is over the 32,768-character limit: the model gets only part of it" in out)

if not WINDOWS:
    import pty
    import signal
    import time

    def spawn(*args, **env):
        """Start teh in a pseudo-terminal; return its process id and the terminal's file descriptor."""
        environment = base_env(**{"TEH_MODEL": "fake", "TEH_SHELL": DEFAULT_SHELL, **env})
        pid, fd = pty.fork()
        if pid == 0:
            os.execve(PY, [PY, "-B", H, *args], environment)
        return pid, fd

    def read_until(fd, marker, seconds=20):
        """Read from the terminal until marker shows (or seconds pass); return what was read."""
        out, end = b"", time.time() + seconds
        while marker not in out and time.time() < end:
            try:
                out += os.read(fd, 4096)
            except OSError:
                break
        return out

    def read_rest(fd):
        """Read from the terminal until the program exits; return what was read."""
        out = b""
        try:
            while chunk := os.read(fd, 4096):
                out += chunk
        except OSError:
            pass
        return out

    section("in a terminal: Ctrl+C, the thinking timer, colour, signals")
    log = s.script(8772, ["echo one", "sleep 33; echo never"], s.w / "ctrlc.log")
    pid, fd = spawn("go", TEH_BASE_URL="http://127.0.0.1:8772")
    out = read_until(fd, b"instead: ")
    os.write(fd, b"a\n")
    time.sleep(2)
    running = bool(s.processes(r"^sleep 33$"))
    os.write(fd, b"\x03")
    out += read_rest(fd)
    os.waitpid(pid, 0)
    s.check("'a' = no more prompts; Ctrl+C stops the running command, and cancels the turn",
            out.count(b"run? [y]es") == 1 and running and not s.processes(r"^sleep 33$") and b"[cancelled]" in out)
    pid, fd = spawn("hi", TEH_BASE_URL="http://127.0.0.1:8768")
    out = read_rest(fd)
    os.waitpid(pid, 0)
    s.check("a live thinking timer in a terminal, erased, and the time on the status line",
            "thinking… 3s".encode() in out and b"\x1b[K" in out and "· 3.5s ·".encode() in out)
    out = s.pty("\\x04", cwd=big, TEH_BASE_URL="http://127.0.0.1:8766")
    s.check("AGENTS.md over the limit: the warning is bold yellow in a terminal", "\x1b[1;33m! AGENTS.md" in out)
    for sig in ("SIGHUP", "SIGTERM"):
        pid, fd = spawn(TEH_BASE_URL="http://127.0.0.1:8766")
        startup = read_until(fd, b"> ").decode(errors="replace").replace("\r", "")
        folder = next(line.split()[1] for line in startup.splitlines() if line.strip().startswith("scratch "))
        os.kill(pid, getattr(signal, sig))
        os.waitpid(pid, 0)
        time.sleep(0.3)
        s.check(f"{sig} at the prompt: the scratch folder is deleted", not os.path.isdir(folder))

section("scratch folder")
s.check("no scratch folders left behind by any of these runs",
        set(glob.glob(os.path.join(tempfile.gettempdir(), "teh-*"))) <= scratch_before)

s.finish()
