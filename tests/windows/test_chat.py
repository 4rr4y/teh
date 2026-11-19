"""Interactive behaviour (driven by chat_run.py): approvals, refusals, chat commands, the startup segment, chat input
(pastes, typed lines, a \\ at the end of a line), the caching startup line and /clear, /compact, AGENTS.md and the
scratch folder. The Windows counterpart of tests/unix/test_chat.sh, with the chat parts of test_output.sh,
test_caching.sh and test_compact.sh. Ctrl+C is tested in test_output.py; the live thinking timer needs a real console."""
import glob, json, os, subprocess, tempfile
from lib import Suite, SHELLS, PY, TESTS, ENCODING, base_env, section

s = Suite()
s.serve("auth_server.py", s.w / "auth.log")  # 8766: answers "ok"
s.serve("caching_server.py", s.w / "req.log")  # 8781: logs requests; a tool call (echo hi), then "done"
s.serve("compact_server.py", s.w / "compact.log")  # 8786
s.serve("refusal_server.py", 8776, s.w / "roles.log", "anthropic")
s.script(8771, [f"echo {word}" for word in ("one", "two", "three", "four", "five", "six")], s.w / "approvals.log")
s.ready()
scratch_before = set(glob.glob(os.path.join(tempfile.gettempdir(), "teh-*")))

def chat(*inputs, cwd=None, **env):  # -> everything the chat showed (stdout and stderr), inputs marked <<'input'>>
    p = subprocess.run([PY, "-B", str(TESTS / "chat_run.py"), *inputs], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=120, cwd=cwd,  # one stream: the inputs among the output
                       env=base_env(PYTHONUNBUFFERED=1, **{"TEH_MODEL": "fake", "TEH_SHELL": "cmd", **env}))
    return p.stdout.decode(ENCODING, "replace").replace("\r\n", "\n")

section("approvals")
out = chat("go", "", "n", "use findstr instead", "y", "a", TEH_BASE_URL="http://127.0.0.1:8771")
res = s.results(s.w / "approvals.log")
s.check("Enter and n decline; other text declines and is passed on",
        res.get(1, "").strip() == "User declined." and res.get(2, "").strip() == "User declined."
        and res.get(3, "").strip() == "User declined: use findstr instead")
s.check("y runs the command (in cmd)", res.get(4, "").strip() == "four\n[exit 0]")
s.check("a runs it and every later one, without asking again", out.count("instead: ") == 5
        and "five" in res.get(5, "") and "six" in res.get(6, ""))

section("refusals")
out = chat("hi", "again", TEH_BASE_URL="http://127.0.0.1:8776", TEH_FORMAT="anthropic")
s.check("anthropic refusal message",
        "[refused] [the model declined to respond: cyber · This looks like malware development.]" in out)
s.check("after a refusal the next prompt starts clean", (s.w / "roles.log").read_text().splitlines()[1]
        == "request 2 roles: ['user']")

section("the startup segment, per shell")
for sh in SHELLS:
    out = chat(TEH_BASE_URL="http://127.0.0.1:8766", TEH_SHELL=sh)
    s.check(f"{sh}: startup segment: Windows, the shell, scratch folder, Windows exit keys",
            "teh · startup" in out and "  os       Windows" in out and f"  shell    {sh} (" in out
            and "scratch  " in out and "\\teh-" in out and "Ctrl+Z, Enter exits" in out and "agents   none found" in out)

section("chat commands")
out = chat("/effort low", "/help", "hi", "/clear", "/compact", "/hlep", "C:\\Windows\\win.ini", TEH_BASE_URL="http://127.0.0.1:8766")
s.check("/effort: the status line, with the effort", "· fake · low · Σ 0 · ctx 0/262,144 (0%)" in out)
s.check("/help lists the commands", "/budget [tokens N | calls N | off]" in out)
s.check("prompt answered; effort shown in status", "\nok\n" in out and "· fake · low · 0." in out)
s.check("/compact with nothing to compact says so", "nothing to compact: the conversation is empty" in out)
s.check("mistyped command: not sent to the model; a Windows path is a prompt",
        "unknown command /hlep: /help lists them" in out and out.count("· fake · low · 0.") == 2)
out = chat("/budget tokens 900000", "/budget calls x", "hi", "/undo", "/undo", TEH_BASE_URL="http://127.0.0.1:8766")
s.check("/budget changes the budgets; rejects what isn't a whole number",
        "Σ 0 (900,000 budget) · ctx 0/262,144 (0%)" in out and "whole number" in out)
s.check("/undo removes the last prompt, then there's nothing left to undo",
        "ctx 0/262,144 (0%)" in out.split("<<'/undo'>>")[1] and "nothing to undo" in out.split("<<'/undo'>>")[2])

section("chat input")
def first_prompt(*inputs):
    (s.w / "req.log").write_text("")
    chat(*inputs, TEH_BASE_URL="http://127.0.0.1:8781/v1", TEH_AUTO=1)
    reqs = s.requests(s.w / "req.log")
    return [m["content"] for r in reqs for m in r["body"]["messages"] if m["role"] == "user"]

s.check("lines pasted at once -> one prompt",
        first_prompt("first line\\nsecond line\\nthird line")[0] == "first line\nsecond line\nthird line")
s.check("a line ending in \\ continues on the next", first_prompt("one \\\\", "two")[0] == "one \ntwo")
prompts = first_prompt("typed one", "typed two")
s.check("lines typed separately -> separate prompts", prompts[0] == "typed one" and "typed two" in prompts)

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
reqs = [l["body"] for l in s.requests(s.w / "compact.log") if "body" in l]
s.check("the summary request carries the focus text", "Also keep: keep the db details" in reqs[2]["messages"][-1]["content"])
s.check("the next prompt follows the summary", [m["content"][:20] for m in reqs[3]["messages"][1:]]
        == ["[This conversation w", "second task"])

section("AGENTS.md")
repo = s.w / "b" / "repo"
(repo / ".git").mkdir(parents=True)
(repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
(repo / "AGENTS.md").write_text("RULE-1")
(repo / "sub").mkdir()
(s.w / "b" / "AGENTS.md").write_text("ABOVE")
r = s.teh("hi", cwd=repo / "sub", env=dict(TEH_BASE_URL="http://127.0.0.1:8766", TEH_MODEL="fake"))
s.check("from a subfolder: the project root's AGENTS.md (a Windows path), nothing above the root",
        f"· using {repo}\\AGENTS.md (6 characters" in r.err and str(s.w / "b" / "AGENTS.md") not in r.err)
r = s.teh("hi", cwd=repo, env=dict(TEH_BASE_URL="http://127.0.0.1:8766", TEH_MODEL="fake", TEH_AGENTS_MD=0))
s.check("TEH_AGENTS_MD=0 turns it off", "using" not in r.err)
out = chat(cwd=repo, TEH_BASE_URL="http://127.0.0.1:8766")
s.check("chat: the agents line names it", f"agents   {repo}\\AGENTS.md (6 characters, added" in out)

section("scratch folder")
s.check("no scratch folders left behind by any of these runs",
        set(glob.glob(os.path.join(tempfile.gettempdir(), "teh-*"))) <= scratch_before)

s.finish()
