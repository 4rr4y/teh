#!/bin/bash
# Interactive behaviour (run in a pseudo-terminal): approvals, Ctrl+C, refusals, the thinking timer, chat commands,
# the scratch folder and AGENTS.md.
source "$(dirname "$0")/lib.sh"
PTY="$TESTS/pty_run.py"
T=${TMPDIR:-/tmp}

serve auth_server.py "$W/auth.log"
serve slow_server.py
printf '%s\n---\n%s\n---\n%s\n---\n%s\n---\n%s' 'echo one' 'echo two' 'echo three' 'echo four' 'echo five' > "$W/cmds2.txt"
serve script_server.py 8771 "$W/cmds2.txt" "$W/results2.log"
printf '%s\n---\n%s\n---\n%s\n---\n%s' 'echo one' 'echo two' 'echo three' 'sleep 33; echo never' > "$W/cmds3.txt"
serve script_server.py 8772 "$W/cmds3.txt" "$W/results3.log"
serve refusal_server.py 8773 /dev/null anthropic
serve refusal_server.py 8776 "$W/roles.log" anthropic  # its own server: only the first request it gets is refused
serve refusal_server.py 8774 /dev/null refusal
serve refusal_server.py 8775 /dev/null filter
ready
scratch_before=$(ls -d "$T"/teh-* 2>/dev/null | wc -l)

echo "== approvals and Ctrl+C"
TEH_BASE_URL=http://127.0.0.1:8771 TEH_MODEL=fake TEH_SHELL=bash H="$H" timeout 30 python3 -B - <<'PY' >/dev/null
import os, pty, time
pid, fd = pty.fork()
if pid == 0: os.execvp("python3", ["python3", "-B", os.environ["H"], "go"])
out = b""
for answer in [b"\n", b"n\n", b"use printf instead\n", b"y\n", b"a\n"]:
    while b"instead: " not in out: out += os.read(fd, 4096)
    os.write(fd, answer); out = out.replace(b"instead: ", b"", 1)
time.sleep(1)
PY
check "Enter / n / feedback / y answers" 'grep -A1 "=== result" "$W/results2.log" | grep -v "^--$" | tr "\n" "|" | grep -q "result 1:|User declined.|=== result 2:|User declined.|=== result 3:|User declined: use printf instead|=== result 4:|four|=== result 5:|five"'
out=$(TEH_BASE_URL=http://127.0.0.1:8772 TEH_MODEL=fake TEH_SHELL=bash H="$H" timeout 30 python3 -B - <<'PY'
import os, pty, time, subprocess
pid, fd = pty.fork()
if pid == 0: os.execvp("python3", ["python3", "-B", os.environ["H"], "go"])
out = b""
while b"instead: " not in out: out += os.read(fd, 4096)
os.write(fd, b"a\n"); time.sleep(2); out += os.read(fd, 65536)
running = subprocess.run(["pgrep", "-fx", "sleep 33"], capture_output=True).returncode == 0
os.write(fd, b"\x03"); time.sleep(1)
try:
    while chunk := os.read(fd, 4096): out += chunk
except OSError: pass
gone = subprocess.run(["pgrep", "-fx", "sleep 33"], capture_output=True).returncode != 0
print(f"prompts={out.count(b'run? [y]es')} running={running} gone={gone} cancelled={b'[cancelled]' in out}")
PY
)
check "'a' = no more prompts; Ctrl+C stops the running command ($out)" '[[ "$out" == "prompts=1 running=True gone=True cancelled=True" ]]'

echo "== refusals"
out=$(TEH_FORMAT=anthropic TEH_BASE_URL=http://127.0.0.1:8773 TEH_MODEL=fake python3 -B "$H" hi </dev/null 2>&1); code=$?
check "anthropic refusal message" '[[ "$out" == *"[refused] [the model declined to respond: cyber · This looks like malware development.]"* ]]'
check "openai refusal field" '[[ "$(TEH_BASE_URL=http://127.0.0.1:8774 TEH_MODEL=fake python3 -B "$H" hi </dev/null 2>&1)" == *"declined to respond: I can"*"t help with that."* ]]'
check "content filter" '[[ "$(TEH_BASE_URL=http://127.0.0.1:8775 TEH_MODEL=fake python3 -B "$H" hi </dev/null 2>&1)" == *"blocked by the provider"*"s content filter"* ]]'

echo "== thinking timer"
out=$(TEH_BASE_URL=http://127.0.0.1:8768 TEH_MODEL=fake H="$H" timeout 30 python3 -B - <<'PY'
import os, pty
pid, fd = pty.fork()
if pid == 0: os.execvp("python3", ["python3", "-B", os.environ["H"], "hi"])
out = b""
try:
    while chunk := os.read(fd, 4096): out += chunk
except OSError: pass
print(out.decode())
PY
)
check "live timer in a terminal, erased, time in status" '[[ "$out" == *"thinking… 3s"* && "$out" == *$'"'"'\x1b[K'"'"'* && "$out" == *"· 3.5s ·"* ]]'

echo "== chat mode"
out=$(TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake timeout 30 python3 -B "$PTY" "$H" '/effort low\n' '/help\n' '/clear\n' 'hi\n' '\x04')
check "startup segment lines" '[[ "$out" == *"teh · startup"* && "$out" == *"scratch  "* && "$out" != *"web      "* && "$out" != *"edit     "* && "$out" != *"search   "* && "$out" == *"agents   none found"* && "$out" == *"role     a helpful assistant"* && "$out" == *"keys     Ctrl+C cancels the current turn · Ctrl+D exits"* ]]'
check "/effort, /help, /clear: the status line, no echo" '[[ "$out" == *"· fake · low · Σ 0 · ctx 0/262,144 (0%)"* && "$out" == *"commands:  /budget [tokens N | calls N | off]"* && "$out" != *"effort: low"* && "$out" != *"conversation cleared"* ]]'
check "prompt answered; effort shown in status" '[[ "$out" == *"ok"* && "$out" == *"· fake · low ·"* ]]'
out=$(TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake timeout 30 python3 -B "$PTY" "$H" '/compact\n' '/hlep\n' '/etc/hosts\n' '\x04')
check "/compact with nothing to compact says so" '[[ "$out" == *"nothing to compact: the conversation is empty"* ]]'
check "mistyped command: not sent to the model; a path is a prompt" '[[ "$out" == *"unknown command /hlep: /help lists them"* && $(grep -c "· fake ·" <<< "$out") == 1 ]]'
out=$(TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake TEH_TOKEN_BUDGET=900000 timeout 30 python3 -B "$PTY" "$H" \
    '/budget\n' '/budget calls 5\n' '/budget tokens 2m\n' '/budget off\n' 'hi\n' '/undo\n' '/undo\n' '\x04')
check "/budget changes the budgets, shown on the status line; rejects what isn't a whole number" '[[ "$out" == *"Σ 0 (900,000 budget) · ctx 0/262,144 (0%)"* && "$out" == *"Σ 0 (900,000 budget) · ctx 0/262,144 (0%) · 0/5 calls"* && "$out" == *"usage: /budget"* && "$out" != *"budget: "* ]]'
check "/undo removes the last prompt (the context goes back to 0), then there's nothing left to undo" '[[ "$out" == *"<</undo\\n>>"*"· fake · default · Σ "*" · ctx 0/262,144 (0%)"*"nothing to undo"* ]]'
TEH_FORMAT=anthropic TEH_BASE_URL=http://127.0.0.1:8776 TEH_MODEL=fake timeout 30 python3 -B "$PTY" "$H" 'bad prompt\n' 'good prompt\n' '\x04' >/dev/null
check "after a refusal the next prompt starts clean" '[[ "$(sed -n 2p "$W/roles.log")" == "request 2 roles: ['"'"'user'"'"']" ]]'

echo "== AGENTS.md"
B="$W/agt"; mkdir -p "$B/repo/.git" "$B/repo/sub" "$B/plain/sub" && printf 'rules\n' > "$B/repo/AGENTS.md"
: > "$B/repo/.git/HEAD"  # a Git repository: its root is a project root
printf 'outside the project\n' > "$B/AGENTS.md"; printf 'no project here\n' > "$B/plain/AGENTS.md"
check "AGENTS.md in cwd loaded (one-shot line)" '(cd "$B/repo" && TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake python3 -B "$H" hi </dev/null 2>&1 | grep -q "· using $B/repo/AGENTS.md (6 characters")'
out=$(cd "$B/repo/sub" && TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake python3 -B "$H" hi </dev/null 2>&1)
check "from a subfolder: the project root's AGENTS.md (the folder with .git), but nothing above the root" '[[ "$out" == *"· using $B/repo/AGENTS.md (6 characters"* && "$out" != *"$B/AGENTS.md"* ]]'
check "no project root (.git, .hg, .jj): only the working directory's, not its parent's" '! (cd "$B/plain/sub" && TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake python3 -B "$H" hi </dev/null 2>&1 | grep -q "using")'
check "TEH_AGENTS_MD=0 turns it off" '! (cd "$B/repo" && TEH_AGENTS_MD=0 TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake python3 -B "$H" hi </dev/null 2>&1 | grep -q "using")'
out=$(cd "$B/repo" && TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake timeout 20 python3 -B "$PTY" "$H" '\x04')
check "a small AGENTS.md: no warning at startup" '[[ "$out" == *"agents   $B/repo/AGENTS.md (6 characters, added"* && "$out" != *"! AGENTS.md"* ]]'
mkdir -p "$B/big" && python3 -c 'print("\n".join(f"rule {i}: " + "keep the code tidy " * 3 for i in range(600)) + "\nLAST_RULE")' > "$B/big/AGENTS.md"
serve echo_server.py 'true' "$W/agsys.log"; ready  # logs the system prompt
out=$(cd "$B/big" && TEH_BASE_URL=http://127.0.0.1:8767 TEH_MODEL=fake TEH_AUTO=1 python3 -B "$H" hi </dev/null 2>&1)
check "AGENTS.md over the limit, one-shot: the usual stderr line says it was cut" '[[ "$out" == *"· using $B/big/AGENTS.md ("*" characters, over the 32,768 limit: only the first "*" were added to the system prompt)"* ]]'
check "the model gets its start, cut at a line break, and where to read the rest" 'grep -q "^rule 0: " "$W/agsys.log" && ! grep -q LAST_RULE "$W/agsys.log" && grep -q "^\[… AGENTS.md is cut here: it has [0-9,]* characters. Read the rest from $B/big/AGENTS.md when it'"'"'s relevant\]" "$W/agsys.log" && grep -B1 "^\[… AGENTS.md is cut" "$W/agsys.log" | head -1 | grep -q "tidy $"'
out=$(cd "$B/big" && TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake timeout 20 python3 -B "$PTY" "$H" '\x04')
check "AGENTS.md over the limit, chat: highlighted at startup" '[[ "$out" == *"keys     "*"! AGENTS.md is over the 32,768-character limit: the model gets only part of it"* && "$out" == *$'"'"'\x1b[1;33m! AGENTS.md'"'"'* ]]'

echo "== scratch folder"
for sig in HUP TERM; do
  left=$(TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake SIG=$sig H="$H" timeout 30 python3 -B - <<'PY'
import os, pty, signal, time
pid, fd = pty.fork()
if pid == 0: os.execvp("python3", ["python3", "-B", os.environ["H"]])
out = b""
while b">" not in out: out += os.read(fd, 4096)
folder = [l.split()[1] for l in out.decode().replace("\r", "").splitlines() if l.strip().startswith("scratch ")][0]
os.kill(pid, getattr(signal, "SIG" + os.environ["SIG"])); os.waitpid(pid, 0); time.sleep(0.3)
print(os.path.isdir(folder))
PY
)
  check "SIG$sig at the prompt: scratch folder deleted" '[[ "$left" == False ]]'
done
check "no scratch folders left behind" '[[ $(ls -d "$T"/teh-* 2>/dev/null | wc -l) == $scratch_before ]]'

finish
