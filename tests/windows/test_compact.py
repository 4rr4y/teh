"""Compaction: automatic when the context window is full, and what happens when it fails. The Windows counterpart of
tests/unix/test_compact.sh (its chat part, /compact, is in test_chat.py)."""
import json
from lib import Suite, section

s = Suite()
LOG = s.w / "req.log"
s.serve("compact_server.py", LOG)
s.ready()

def logged():  # -> (request bodies, transcripts the server read back)
    lines = s.requests(LOG)
    return [l["body"] for l in lines if "body" in l], [l["transcript"] for l in lines if "transcript" in l]

section("automatic, when the window is full (mid-turn)")
LOG.write_text("")
r = s.teh("please go", env=dict(TEH_BASE_URL="http://127.0.0.1:8786/v1", TEH_MODEL="m", TEH_AUTO=1, TEH_SHELL="cmd",
                                TEH_CONTEXT_WINDOW=1000, TEH_OUTPUT="json"))
d = json.loads(r.out) if r.out.strip().startswith("{") else {}
reqs, T = logged()
s.check("the run carries on after compacting, exit 0", r.code == 0 and d.get("answer") == "continued after compaction"
        and d.get("compactions") == 1)
s.check("status line says it compacted", "context window full (1,005/1,000 tokens): compacting" in r.err
        and "compacted: 1,0" in r.err)
s.check("summary request = the whole conversation, unchanged, plus one request",
        reqs[1]["messages"][:len(reqs[0]["messages"])] == reqs[0]["messages"] and reqs[1]["tools"] == reqs[0]["tools"]
        and "about to be compacted" in reqs[1]["messages"][-1]["content"])
s.check("the conversation afterwards: system prompt + one message", len(reqs[2]["messages"]) == 2)
s.check("it keeps the request word for word, the summary, and the transcript's Windows path",
        all(x in reqs[2]["messages"][1]["content"] for x in ("1. please go", "SUMMARY-TEXT", "\\transcript-1.txt")))
s.check("the transcript has the prompt, the command and its output (as cmd ran it)",
        T and all(x in T[0] for x in ("## user\nplease go", "## command\necho hi", "## output\nhi")))

section("when compaction fails")
LOG.write_text("")
r = s.teh("go", env=dict(TEH_BASE_URL="http://127.0.0.1:8786/fail/v1", TEH_MODEL="m", TEH_AUTO=1, TEH_SHELL="cmd",
                         TEH_CONTEXT_WINDOW=1000))
s.check("a clear message, and exit 3 (context window full)", r.code == 3 and "compaction failed (HTTP 400" in r.err)

s.finish()
