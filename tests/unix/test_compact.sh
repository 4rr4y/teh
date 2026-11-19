#!/bin/bash
# Compaction: automatic when the context window is full, /compact in chat, and what happens when it fails.
source "$(dirname "$0")/lib.sh"
PTY="$TESTS/pty_run.py"
LOG="$W/req.log"
serve compact_server.py "$LOG"
ready
q() {  # q <condition>: true if the condition holds for the logged requests (reqs) and transcripts (T)
    python3 -c "import json, sys; L=[json.loads(l) for l in open('$LOG')]; reqs=[l['body'] for l in L if 'body' in l]; T=[l['transcript'] for l in L if 'transcript' in l]; sys.exit(not ($1))"
}

echo "== automatic, when the window is full (mid-turn)"
: > "$LOG"
out=$(TEH_BASE_URL=http://127.0.0.1:8786/v1 TEH_MODEL=m TEH_AUTO=1 TEH_CONTEXT_WINDOW=1000 TEH_OUTPUT=json \
      python3 -B "$H" "please go" </dev/null 2>"$W/err"); code=$?
check "the run carries on after compacting, exit 0" '[[ $code == 0 ]] && [[ "$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d[\"answer\"], d[\"compactions\"])" "$out")" == "continued after compaction 1" ]]'
check "status line says it compacted" 'grep -qE "compacted: 1,0[0-9][0-9] → about" "$W/err" && grep -q "context window full (1,005/1,000 tokens): compacting" "$W/err"'
check "summary request = the whole conversation, unchanged, plus one request (so it's a cache hit)" 'q "reqs[1][\"messages\"][:len(reqs[0][\"messages\"])] == reqs[0][\"messages\"] and reqs[1][\"tools\"] == reqs[0][\"tools\"] and \"about to be compacted\" in reqs[1][\"messages\"][-1][\"content\"]"'
check "the conversation afterwards: system prompt + one message" 'q "len(reqs[2][\"messages\"]) == 2"'
check "it keeps the request word for word, the summary, and the transcript's path" 'q "all(x in reqs[2][\"messages\"][1][\"content\"] for x in (\"1. please go\", \"SUMMARY-TEXT\", \"/transcript-1.txt\"))"'
check "the transcript has the prompt, the command and its output" 'q "all(x in T[0] for x in (\"## user\\nplease go\", \"## command\\necho hi\", \"## output\\nhi\"))"'

echo "== /compact in chat"
: > "$LOG"
TEH_BASE_URL=http://127.0.0.1:8786/v1 TEH_MODEL=m TEH_AUTO=1 timeout 30 python3 -B "$PTY" "$H" \
  'first task\n' '/compact keep the db details\n' 'second task\n' '\x04' > "$W/chat"
check "the summary request carries the focus text" 'q "\"Also keep: keep the db details\" in reqs[2][\"messages\"][-1][\"content\"]"'
check "the next prompt follows the summary" 'q "[m[\"content\"][:20] for m in reqs[3][\"messages\"][1:]] == [\"[This conversation w\", \"second task\"]"'
check "/help lists /compact" '[[ "$(python3 -B "$H" --help 2>&1)" == *"/compact [what to keep]"* ]]'

echo "== when compaction fails"
: > "$LOG"
TEH_BASE_URL=http://127.0.0.1:8786/fail/v1 TEH_MODEL=m TEH_AUTO=1 TEH_CONTEXT_WINDOW=1000 python3 -B "$H" "go" \
  </dev/null >/dev/null 2>"$W/err"; code=$?
check "a clear message, and exit 3 (context window full)" '[[ $code == 3 ]] && grep -q "compaction failed (HTTP 400" "$W/err"'

finish
