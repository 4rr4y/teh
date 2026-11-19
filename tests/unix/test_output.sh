#!/bin/bash
# One-shot results for scripts: exit codes for each way a run can end, and TEH_OUTPUT=json.
# Also chat input: a pasted block is one prompt, and a line ending in \ continues on the next.
source "$(dirname "$0")/lib.sh"
PTY="$TESTS/pty_run.py"
serve auth_server.py "$W/auth.log"         # 8766: answers "ok"
serve loop_server.py                       # 8765: always calls a tool, reports huge usage
serve errors_server.py                     # 8782: /cut/, /400/
serve slow_server.py                       # 8768: answers after 3.5s
serve refusal_server.py 8774 /dev/null refusal
printf '%s\n---\n%s' 'echo one' 'exit 7' > "$W/cmds.txt"
serve script_server.py 8771 "$W/cmds.txt" /dev/null
serve caching_server.py "$W/req.log"       # 8781: logs request bodies
ready
oneshot() { env "$@" python3 -B "$H" go </dev/null >"$W/out" 2>"$W/err"; echo $?; }

echo "== exit codes"
check "done -> 0" '[[ $(oneshot TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=m) == 0 ]]'
check "error (HTTP 400) -> 1" '[[ $(oneshot TEH_BASE_URL=http://127.0.0.1:8782/400 TEH_MODEL=m) == 1 ]]'
check "refused -> 2" '[[ $(oneshot TEH_BASE_URL=http://127.0.0.1:8774 TEH_MODEL=m) == 2 ]]'
check "context window full -> 3" '[[ $(oneshot TEH_BASE_URL=http://127.0.0.1:8765 TEH_MODEL=m TEH_AUTO=1 TEH_CONTEXT_WINDOW=1000) == 3 ]]'
check "reply cut off -> 4" '[[ $(oneshot TEH_BASE_URL=http://127.0.0.1:8782/cut TEH_MODEL=m) == 4 ]]'
check "no budget by default: a run of 3 model calls finishes" '[[ $(oneshot TEH_BASE_URL=http://127.0.0.1:8771 TEH_MODEL=m TEH_AUTO=1) == 0 ]]'
check "turn budget reached -> 5, before the call that would pass it, with calls on the status line" '[[ $(oneshot TEH_BASE_URL=http://127.0.0.1:8771 TEH_MODEL=m TEH_AUTO=1 TEH_TURN_BUDGET=1) == 5 && $(grep -c "^\$ " "$W/err") == 1 && "$(cat "$W/err")" == *"(0%) · 1/1 calls"*"turn budget reached: 1 model calls for this prompt (TEH_TURN_BUDGET=1)"* ]]'
check "a turn budget the run fits in: no effect" '[[ $(oneshot TEH_BASE_URL=http://127.0.0.1:8771 TEH_MODEL=m TEH_AUTO=1 TEH_TURN_BUDGET=3) == 0 ]]'
check "token budget reached -> 5, with the budget on the status line" '[[ $(oneshot TEH_BASE_URL=http://127.0.0.1:8765 TEH_MODEL=m TEH_AUTO=1 TEH_CONTEXT_WINDOW=100000000 TEH_TOKEN_BUDGET=2000000) == 5 && $(grep -c "· fake ·" "$W/err") == 1 && "$(cat "$W/err")" == *"Σ 1,238,888 (1,000,000 cached | 2,000,000 budget) · ctx"*"token budget reached: 1,238,888 tokens used, and the next call would need about 1,238,"*" more (TEH_TOKEN_BUDGET=2,000,000, for the whole run)"* ]]'
out=$(env TEH_BASE_URL=http://127.0.0.1:8771 TEH_MODEL=m TEH_AUTO=1 TEH_TURN_BUDGET=1 TEH_OUTPUT=json python3 -B "$H" go </dev/null 2>/dev/null)
check "TEH_OUTPUT=json: ended budget, with why, and the commands that ran" '[[ "$(python3 -c "import json,sys; r=json.loads(sys.argv[1]); print(r[\"ended\"], len(r[\"commands\"]), \"turn budget\" in r[\"error\"])" "$out")" == "budget 1 True" ]]'
set -m  # job control on: otherwise bash starts background jobs with Ctrl+C (SIGINT) ignored
TEH_BASE_URL=http://127.0.0.1:8768 TEH_MODEL=m python3 -B "$H" go </dev/null >/dev/null 2>&1 & pid=$!
set +m
sleep 1; kill -INT $pid; wait $pid; code=$?
check "cancelled (Ctrl+C) -> 130" '[[ $code == 130 ]]'

W2=$(mktemp -d); printf '%s' 'echo hi' > "$W2/c.txt"; serve script_server.py 8773 "$W2/c.txt" /dev/null; ready
out=$(cd "$W2" && setsid -w bash -c "TEH_BASE_URL=http://127.0.0.1:8773 TEH_MODEL=m python3 -B '$H' go </dev/null 2>&1; echo \"exit \$?\"")
check "no terminal and no TEH_AUTO: a clear error, exit 1" '[[ "$out" == *"no terminal to approve commands: set TEH_AUTO=1"*"exit 1"* ]]'
rm -rf "$W2"

echo "== TEH_OUTPUT=json"
oneshot TEH_BASE_URL=http://127.0.0.1:8771 TEH_MODEL=m TEH_AUTO=1 TEH_OUTPUT=json >/dev/null
j() { python3 -c "import json, sys; d=json.load(open('$W/out')); sys.exit(not ($1))"; }  # j <condition on d>
check "stdout is exactly one JSON object" 'python3 -c "import json; json.load(open(\"$W/out\"))"'
check "ended done, answer, model, no error" 'j "(d[\"ended\"], d[\"answer\"], d[\"model\"], d[\"error\"]) == (\"done\", \"done\", \"m\", None)"'
check "commands with their exit codes" 'j "d[\"commands\"] == [{\"command\": \"echo one\", \"exit\": 0}, {\"command\": \"exit 7\", \"exit\": 7}]"'
check "token totals" 'j "d[\"tokens\"] == {\"input\": 30, \"cached\": 0, \"output\": 3, \"context\": 11}"'
check "answer not also printed as text; status still on stderr" '[[ $(wc -l < "$W/out") == 1 ]] && grep -q "· fake · default" "$W/err"'
oneshot TEH_BASE_URL=http://127.0.0.1:8774 TEH_MODEL=m TEH_OUTPUT=json >/dev/null
check "refusal: ended refused, with the reason" 'j "d[\"ended\"] == \"refused\" and \"help with that\" in d[\"error\"]"'

echo "== chat input"
first_prompt() { python3 -c "import json; r=json.loads(open('$W/req.log').readline()); print(repr(r['body']['messages'][1]['content']))"; }
: > "$W/req.log"
TEH_BASE_URL=http://127.0.0.1:8781/v1 TEH_MODEL=m TEH_AUTO=1 timeout 30 python3 -B "$PTY" "$H" 'first line\nsecond line\nthird line\n' '\x04' >/dev/null
check "lines pasted at once (no paste markers) -> one prompt" '[[ "$(first_prompt)" == "'"'"'first line\\nsecond line\\nthird line'"'"'" ]]'
: > "$W/req.log"
TEH_BASE_URL=http://127.0.0.1:8781/v1 TEH_MODEL=m TEH_AUTO=1 timeout 30 python3 -B "$PTY" "$H" '\x1b[200~alpha\nbeta\x1b[201~\r' '\x04' >/dev/null
check "bracketed paste (terminal paste markers) -> one prompt" '[[ "$(first_prompt)" == "'"'"'alpha\\nbeta'"'"'" ]]'
: > "$W/req.log"
TEH_BASE_URL=http://127.0.0.1:8781/v1 TEH_MODEL=m TEH_AUTO=1 timeout 30 python3 -B "$PTY" "$H" 'one \\\n' 'two\n' '\x04' >/dev/null
check "a line ending in \\ continues on the next" '[[ "$(first_prompt)" == "'"'"'one \\ntwo'"'"'" ]]'
: > "$W/req.log"
TEH_BASE_URL=http://127.0.0.1:8781/v1 TEH_MODEL=m TEH_AUTO=1 timeout 30 python3 -B "$PTY" "$H" 'typed one\n' 'typed two\n' '\x04' >/dev/null
check "lines typed separately -> separate prompts" '[[ "$(first_prompt)" == "'"'"'typed one'"'"'" ]] && grep -q "typed two" "$W/req.log"'

finish
