#!/bin/bash
# Startup and settings, the status line and context limit, shells, the Anthropic format, running commands.
source "$(dirname "$0")/lib.sh"

serve loop_server.py
serve auth_server.py "$W/auth.log"
serve anthropic_server.py 8779 "$W/anth.log"
serve echo_server.py 'echo "shell=$0 quote=\"it'"'"'s\""; exit 3' "$W/sys.log"
printf '%s\n---\n%s\n---\n%s\n---\n%s\n---\n%s' 'sleep 31 & echo server started' 'read x; echo "got:[$x]"' \
  'echo before; sleep 32; echo never' 'seq 1 20000' 'echo to-stdout; echo to-stderr >&2; echo to-stdout-again' > "$W/cmds.txt"
printf '\n---\n%s' 'wc -l < "$TEH_SCRATCH/output-1.txt"; tail -1 "$TEH_SCRATCH/output-1.txt"' >> "$W/cmds.txt"
serve script_server.py 8770 "$W/cmds.txt" "$W/results.log"
printf '%s' 'echo "seen: $(env | grep ^TEH_ | cut -d= -f1 | sort | tr "\n" " ")key=[$TEH_API_KEY] scratch=[$TEH_SCRATCH]"' > "$W/envcmd.txt"
printf '%s\n---\n%s' 'command -v teh-fetch; teh-fetch 2>&1 | head -1' \
  'printf "\033[31mred\033[0m\nload 10%%\rload 100%%\n"; for i in 1 2 3 4 5 6; do echo same line, printed again and again; done' > "$W/tidycmd.txt"
serve script_server.py 8785 "$W/tidycmd.txt" "$W/tidy.log"
printf '%s' 'sleep 3; echo finished' > "$W/slowcmd.txt"
serve script_server.py 8787 "$W/slowcmd.txt" "$W/slow.log"
serve script_server.py 8783 "$W/envcmd.txt" "$W/env.log"
ready

echo "== startup / settings"
check "--help shows usage" '[[ "$(python3 -B "$H" --help 2>&1)" == *"TEH_CONTEXT_WINDOW=<n>"* ]]'
out=$(env -u TEH_MODEL -u TEH_BASE_URL python3 -B "$H" x </dev/null 2>&1); code=$?
check "no settings -> usage, exit 1" '[[ $code == 1 && "$out" == *usage:* ]]'
out=$(TEH_BASE_URL=anthropic TEH_THINKING=100 python3 -B "$H" x </dev/null 2>&1)
check "TEH_THINKING without TEH_MODEL -> usage, no crash" '[[ "$out" == *usage:* && "$out" != *Traceback* ]]'
check "bad TEH_BASE_URL -> clear error" '[[ "$(TEH_BASE_URL=nope TEH_MODEL=m python3 -B "$H" x </dev/null 2>&1)" == *"not a URL or a known provider"* ]]'
out=$(env -u TEH_MODEL TEH_BASE_URL=anthropic TEH_MODLE=x python3 -B "$H" x </dev/null 2>&1)
check "misspelt setting: warning with a suggestion" '[[ "$out" == *"unknown setting TEH_MODLE: did you mean TEH_MODEL?"* ]]'
check "setting that must be a number" '[[ "$(TEH_BASE_URL=anthropic TEH_MODEL=m TEH_MAX_TOKENS=16k python3 -B "$H" x </dev/null 2>&1)" == "TEH_MAX_TOKENS must be a whole number, not '"'"'16k'"'"'" ]]'
check "missing TEH_SHELL -> clear error" '[[ "$(TEH_BASE_URL=anthropic TEH_MODEL=m TEH_SHELL=nosuch python3 -B "$H" x </dev/null 2>&1)" == *"not found; set TEH_SHELL"* ]]'

echo "== context window + status line"
out=$(TEH_BASE_URL=http://127.0.0.1:8765 TEH_MODEL=fake TEH_AUTO=1 TEH_CONTEXT_WINDOW=1000000 python3 -B "$H" go </dev/null 2>&1)
check "status line with commas" '[[ "$out" == *"in 1,234,567 (1,000,000 cached) · out 4,321 · Σ 1,238,888 (1,000,000 cached) · ctx 1,238,888/1,000,000 (124%)"* ]]'
check "context full: compacts once, then stops if still full (no endless loop)" '[[ "$out" == *"context window full (1,238,888/1,000,000 tokens): compacting"* && $(grep -c "compacted:" <<< "$out") == 1 && "$out" == *"still full right after compacting: stopping"* ]]'
check "default context window 262,144" '[[ "$(TEH_BASE_URL=http://127.0.0.1:8766 TEH_MODEL=fake python3 -B "$H" hi </dev/null 2>&1)" == *"/262,144"* ]]'
: > "$W/auth.log"; TEH_BASE_URL=http://127.0.0.1:8766 TEH_API_KEY=k1 TEH_MODEL=fake python3 -B "$H" hi </dev/null >/dev/null 2>&1
check "TEH_API_KEY sent as Bearer" 'grep -q "Bearer k1" "$W/auth.log"'

echo "== shells"
for sh in bash sh dash; do
  command -v $sh >/dev/null || continue
  out=$(TEH_BASE_URL=http://127.0.0.1:8767 TEH_MODEL=fake TEH_AUTO=1 TEH_SHELL=$sh python3 -B "$H" go </dev/null 2>/dev/null)
  check "TEH_SHELL=$sh: runs in $sh, quoting intact, exit code" '[[ "$out" == *"shell=$(command -v $sh) quote=\"it'"'"'s\""*"[exit 3]"* || "$out" == *"shell=/usr/bin/$sh quote=\"it'"'"'s\""*"[exit 3]"* ]]'
done
out=$(TEH_BASE_URL=http://127.0.0.1:8767 TEH_MODEL=fake TEH_AUTO=1 SHELL=dash python3 -B "$H" go </dev/null 2>/dev/null)
check "no TEH_SHELL: the system's \$SHELL is used" '[[ "$out" == *"shell=$(command -v dash) quote"* || "$out" == *"shell=/usr/bin/dash quote"* ]]'
out=$(TEH_BASE_URL=http://127.0.0.1:8767 TEH_MODEL=fake TEH_AUTO=1 SHELL=dash TEH_SHELL=bash python3 -B "$H" go </dev/null 2>/dev/null)
check "TEH_SHELL wins over \$SHELL" '[[ "$out" == *"shell=$(command -v bash) quote"* || "$out" == *"shell=/usr/bin/bash quote"* ]]'
check "system prompt names OS, shell, scratch, no-input rule, web helper" 'grep -q "OS: " "$W/sys.log" && grep -qE "Shell: [a-z]+; use its syntax" "$W/sys.log" && grep -q "Temporary files (scripts, downloads, notes) go in" "$W/sys.log" && grep -q "non-interactive" "$W/sys.log" && grep -q "the only way to access the web" "$W/sys.log"'
check "system prompt: search, its sources, and that general search engines don't work" 'grep -qF "Search: \`teh-fetch --search SOURCE[:OPTION] QUERY\`, SOURCE one of wikipedia, " "$W/sys.log" && grep -q "general web search engines don.t work" "$W/sys.log"'
check "default role" 'grep -q "^You are a helpful assistant, with shell access" "$W/sys.log"'
TEH_BASE_URL=http://127.0.0.1:8767 TEH_MODEL=fake TEH_AUTO=1 TEH_ROLE="a careful sysadmin on a production server" \
  python3 -B "$H" go </dev/null >/dev/null 2>&1
check "TEH_ROLE sets the role" 'grep -q "^You are a careful sysadmin on a production server, with shell access" "$W/sys.log"'
out=$(TEH_BASE_URL=http://127.0.0.1:8767 TEH_MODEL=fake TEH_AUTO=1 python3 -B "$H" go </dev/null 2>&1 >/dev/null)
check "stderr has no colour codes when piped" '[[ "$out" != *$'"'"'\x1b'"'"'* ]]'

echo "== the model's commands don't see teh's settings"
TEH_BASE_URL=http://127.0.0.1:8783 TEH_MODEL=m TEH_AUTO=1 TEH_API_KEY=sk-SECRET TEH_EFFORT=low TEH_MODLE=x \
  python3 -B "$H" go </dev/null >/dev/null 2>&1
check "only TEH_SCRATCH is visible, not the key or other settings" 'grep -q "seen: TEH_SCRATCH key=\[\] scratch=\[/" "$W/env.log"'
check "TEH_SCRATCH is the session's scratch folder" 'grep -qE "scratch=\[[^]]*/teh-[^]/]+\]" "$W/env.log"'

echo "== the web helper's short name, and tidied output"
mkdir -p "$W/p" && (cd "$W/p" && TEH_BASE_URL=http://127.0.0.1:8785 TEH_MODEL=m TEH_AUTO=1 python3 -B "$H" go </dev/null >/dev/null 2>&1)
check "commands find teh-fetch in the scratch folder, and it runs the helper" 'grep -A2 "result 1" "$W/tidy.log" | grep -q "/teh-[^/]*/teh-fetch" && grep -A2 "result 1" "$W/tidy.log" | grep -q "usage: teh.py --fetch"'
check "output tidied: no colour codes, progress bar's final state, repeats counted" 'grep -A5 "result 2" "$W/tidy.log" | tr "\n" "|" | grep -q "red|load 100%|same line, printed again and again|\[… the line above repeated 5 more times\]"'
check "system prompt: teh-fetch and its options, no narration, read selectively" 'grep -qF "run \`teh-fetch [-H '"'"'Name: value'"'"'] [-X METHOD] [-d DATA | --json DATA] URL [word ...]\`, the only way" "$W/sys.log" && grep -q "no preamble or narration" "$W/sys.log" && grep -q "read only what you need" "$W/sys.log"'

echo "== Anthropic format"
out=$(TEH_FORMAT=anthropic TEH_BASE_URL=http://127.0.0.1:8779 TEH_MODEL=fake TEH_AUTO=1 python3 -B "$H" go </dev/null 2>&1)
check "tool_use -> tool_result -> answer" '[[ "$out" == *"RESULT: hi from anthropic"* && "$out" == *"[exit 0]"* ]]'
check "anthropic tool shape + API version" 'grep -q "\"input_schema\"" "$W/anth.log" && grep -q "2026-10-21" "$W/anth.log"'
check "cached tokens counted in input" '[[ "$out" == *"in 1,005 (1,000 cached)"* ]]'

echo "== commands (with TEH_COMMAND_TIMEOUT=3, so timeouts are quick)"
t0=$(date +%s.%N); TEH_BASE_URL=http://127.0.0.1:8770 TEH_MODEL=fake TEH_AUTO=1 TEH_SHELL=bash TEH_COMMAND_TIMEOUT=3 python3 -B "$H" go </dev/null >/dev/null 2>&1
dt=$(echo "$(date +%s.%N) - $t0" | bc)
check "background job returns at once (run took ${dt:0:4}s, 3s of it the timeout)" '(( $(echo "$dt < 5" | bc) ))'
check "background job still running" 'pgrep -fx "sleep 31" >/dev/null'; pgrep -fx 'sleep 31' | xargs -r kill
check "timed-out command stopped" '! pgrep -fx "sleep 32" >/dev/null'
check "stdin is empty" 'grep -q "got:\[\]" "$W/results.log"'
check "partial output kept on timeout" 'grep -A1 "result 3" "$W/results.log" | grep -q before && grep -q "timed out after 3s" "$W/results.log"'
check "long output: first and last lines, cut at line breaks" 'grep -A1 "=== result 4" "$W/results.log" | grep -q "^1$" && grep -B3 "=== result 5" "$W/results.log" | grep -q "^20000$"'
check "the note says how much, and where the full output is" 'grep -qE "\[… [0-9,]+ characters \([0-9,]+ lines\) omitted; full output in .*/teh-[^/]+/output-1.txt: use grep or sed -n to read it\]" "$W/results.log"'
check "a later command can read the full output" 'grep -A2 "=== result 6" "$W/results.log" | tr "\n" " " | grep -q "20000 20000"'
: > "$W/slow.log"; TEH_BASE_URL=http://127.0.0.1:8787 TEH_MODEL=m TEH_AUTO=1 TEH_COMMAND_TIMEOUT=1 python3 -B "$H" go </dev/null >/dev/null 2>&1
check "TEH_COMMAND_TIMEOUT=1: stopped, and the message says 1s" 'grep -q "timed out after 1s" "$W/slow.log"'
: > "$W/slow.log"; TEH_BASE_URL=http://127.0.0.1:8787 TEH_MODEL=m TEH_AUTO=1 TEH_COMMAND_TIMEOUT=0 python3 -B "$H" go </dev/null >/dev/null 2>&1
check "TEH_COMMAND_TIMEOUT=0: no limit, the command finishes" 'grep -q "^finished" "$W/slow.log" && ! grep -q "timed out" "$W/slow.log"'
check "stdout/stderr merged in order" 'grep -A3 "result 5" "$W/results.log" | tr "\n" " " | grep -q "to-stdout to-stderr to-stdout-again"'

echo "== the edit helper, as the model runs it: teh-edit with a heredoc"
cat > "$W/editcmd.txt" <<'CMDS'
printf 'x = 1\ny = 2\n' > f.py && teh-edit f.py <<'EOF'
<<<<<<< SEARCH
x = 1
=======
x = 10
>>>>>>> REPLACE
EOF
cat f.py
---
true
CMDS
serve script_server.py 8792 "$W/editcmd.txt" "$W/edit.log"; ready
TEH_BASE_URL=http://127.0.0.1:8792 TEH_MODEL=m TEH_AUTO=1 python3 -B "$H" go </dev/null >/dev/null 2>&1
check "teh-edit is found, applies the block, and the file is changed" 'grep -A5 "=== result 1:" "$W/edit.log" | tr "\n" "|" | grep -q "edited f.py: 1 of 1 blocks applied (at line 1)|x = 10|y = 2|\[exit 0\]"'
check "no blank line before the exit code; no output at all: only the exit code" 'grep -A1 "=== result 2:" "$W/edit.log" | tr "\n" "|" | grep -qx "=== result 2:|\[exit 0\]|"'
check "system prompt: edit with teh-edit, all of a file's blocks in one call" 'grep -qF "Edit files with \`teh-edit FILE\`, given on stdin blocks of: <<<<<<< SEARCH, the exact current lines, =======, the new lines, >>>>>>> REPLACE; send all of a file'"'"'s blocks in one call" "$W/sys.log"'

echo "== a runaway command: stopped once its output passes the cap"
printf '%s\n---\n%s' 'yes' 'head -c 6000000 /dev/zero | tr "\0" "y"' > "$W/flood.txt"
serve script_server.py 8789 "$W/flood.txt" "$W/flood.log"; ready
start=$SECONDS
timeout 60 env TEH_BASE_URL=http://127.0.0.1:8789 TEH_MODEL=m TEH_AUTO=1 TEH_COMMAND_TIMEOUT=0 python3 -B "$H" go </dev/null >/dev/null 2>&1; code=$?
check "yes, with no timeout: stopped at 5,000,000 bytes, quickly, and the run carries on" '[[ $code == 0 && $((SECONDS - start)) -lt 30 ]] && grep -A5 "=== result 1:" "$W/flood.log" | grep -q "^\[stopped: its output passed 5,000,000 bytes. Write large output to a file"'
check "a fast burst over the cap: cut off, with a note either way" 'grep -A5 "=== result 2:" "$W/flood.log" | grep -qE "^\[(stopped: its output passed 5,000,000 bytes|exit 0\] \[output cut off at 5,000,000 bytes)"'

echo "== a command run again: only what changed"
C='seq 1 200; cat "$TEH_SCRATCH/n" 2>/dev/null; echo changed > "$TEH_SCRATCH/n"'  # prints one more line from run 2
printf '%s\n---\n%s\n---\n%s' "$C" "$C" "$C" > "$W/rerun.txt"
serve script_server.py 8788 "$W/rerun.txt" "$W/rerun.log"; ready
TEH_BASE_URL=http://127.0.0.1:8788 TEH_MODEL=m TEH_AUTO=1 python3 -B "$H" go </dev/null >/dev/null 2>&1
check "first run: the whole output" 'grep -A200 "=== result 1:" "$W/rerun.log" | grep -q "^150$"'
check "second run: only the changed lines, with a line around them" 'grep -A5 "=== result 2:" "$W/rerun.log" | tr "\n" "|" | grep -q "the lines that changed since the last time this command ran.*| 200|+changed|\[exit 0\]" && ! grep -A6 "=== result 2:" "$W/rerun.log" | grep -q "^150$"'
check "third run, identical: one line" 'grep -A2 "=== result 3:" "$W/rerun.log" | tr "\n" "|" | grep -q "^=== result 3:|\[the same output as the last time this command ran\]|\[exit 0\]|"'

finish
