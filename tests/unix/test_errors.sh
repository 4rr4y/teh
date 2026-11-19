#!/bin/bash
# Error handling: malformed tool calls are answered instead of ending the turn; retries honour retry-after.
source "$(dirname "$0")/lib.sh"
U=http://127.0.0.1:8782
serve errors_server.py
ready
enc() { python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"; }

echo "== malformed tool calls"
for case in '{not json|not valid JSON' '{}|no command was given' '[1,2]|not a JSON object' '{"command": "   "}|no command was given'; do
  args=${case%%|*}; expect=${case##*|}
  out=$(TEH_BASE_URL=$U/bad/$(enc "$args") TEH_MODEL=m TEH_AUTO=1 python3 -B "$H" go </dev/null 2>&1); code=$?
  check "arguments $args: turn continues, model told '$expect'" '[[ $code == 0 && "$out" == *"RESULT: Not run: "*"$expect"* ]]'
done

echo "== retry-after"
for case in 'retry-after=1|1s|1.0' 'retry-after-ms=1500|1.5s|1.5' 'none=x|2s|2.0'; do
  IFS='|' read -r header shown secs <<< "$case"
  t0=$(date +%s.%N); out=$(TEH_BASE_URL=$U/429/$(enc "$header")/v1 TEH_MODEL=m python3 -B "$H" go </dev/null 2>&1)
  dt=$(printf '%.1f' "$(echo "$(date +%s.%N) - $t0" | bc)")
  check "$header: 'retrying in $shown', waited ~${secs}s (took ${dt}s)" '[[ "$out" == *"retrying in $shown"* ]] && (( $(echo "$dt >= $secs && $dt < $secs + 0.8" | bc) ))'
done

finish
