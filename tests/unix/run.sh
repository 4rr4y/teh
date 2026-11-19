#!/bin/bash
# Runs the test suites: tests/unix/run.sh [--changed] [suite ...]   e.g. tests/unix/run.sh core fetch
#   --changed  skips a suite when nothing it depends on has changed since it last passed (see inputs.py). The unit
#              tests always run: they take under a second.
# Needs Linux or macOS (bash, a pseudo-terminal) and Python 3; no API key, no network.
cd "$(dirname "$0")"
changed=0
[ "$1" = --changed ] && { changed=1; shift; }
suites=("$@")
[ ${#suites[@]} = 0 ] && suites=(units core chat caching errors output compact fetch)
PASSED=.passed  # one line per suite: its name and the hash of its inputs when it last passed
touch "$PASSED"
failed=()
skipped=()
for suite in "${suites[@]}"; do
    if [ "$suite" = units ]; then
        echo "######## units"
        out=$(cd .. && python3 -B -m unittest -q test_units 2>&1); status=$?  # shared with other systems
        if [ $status = 0 ]; then tail -3 <<< "$out"; else echo "$out"; fi  # a failure: all of it, to see which and why
    else
        hash=$(python3 -B inputs.py "$suite")
        if [ $changed = 1 ] && grep -qx "$suite $hash" "$PASSED"; then skipped+=("$suite"); continue; fi
        echo "######## $suite"
        bash "test_$suite.sh"; status=$?
        if [ $status = 0 ]; then  # remember it passed with these inputs
            { grep -v "^$suite " "$PASSED"; echo "$suite $hash"; } > "$PASSED.new" && mv "$PASSED.new" "$PASSED"
        fi
    fi
    [ $status = 0 ] || failed+=("$suite")
done
echo
[ ${#skipped[@]} = 0 ] || echo "skipped (nothing they depend on changed since they passed): ${skipped[*]}"
if [ ${#failed[@]} = 0 ]; then echo "all suites passed"; else echo "FAILED: ${failed[*]}"; exit 1; fi
