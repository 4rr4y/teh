# Shared by the test suites (source it): paths, fake servers, and a check() that counts passes and failures.
# Tests run against fake API servers on localhost (tests/fakes/, shared), so they need no API key and cost nothing.

TESTS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
H="$TESTS/../../teh.py"       # the harness under test
FAKES="$TESTS/../fakes"       # shared with other systems' tests
W=$(mktemp -d)                    # work folder for logs and copies; removed at the end
SERVERS=()
PORTS=()                          # their ports, for ready()
pass=0
fail=0

port_of() {  # port_of <fake server file> <its first argument>: the port it listens on
    case "$1" in  # these have their port built in; the others take it as their first argument
        loop_server.py) echo 8765 ;;  auth_server.py) echo 8766 ;;      echo_server.py) echo 8767 ;;
        slow_server.py) echo 8768 ;;  anthropic_server.py) echo 8779 ;; caching_server.py) echo 8781 ;;
        errors_server.py) echo 8782 ;; compact_server.py) echo 8786 ;;  *) echo "$2" ;;
    esac
}
serve() {  # serve <fake server file> [args...]: start a fake server in the background, remembered for stop_servers
    python3 -B "$FAKES/$1" "${@:2}" &
    SERVERS+=($!)
    PORTS+=("$(port_of "$1" "$2")")
}
ready() {  # ready [port ...]: wait until every server started (and these ports) accepts connections, at most 10s
    python3 - "${PORTS[@]}" "$@" <<'EOF'
import socket, sys, time
end = time.time() + 10
for port in map(int, sys.argv[1:]):
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            break
        except OSError:
            time.sleep(0.02)
EOF
}
stop_servers() { for pid in "${SERVERS[@]}"; do kill "$pid" 2>/dev/null; done; SERVERS=(); PORTS=(); }
trap 'stop_servers; rm -rf "$W"' EXIT
cd "$W"                           # a neutral working folder: no project AGENTS.md is picked up

check() {  # check <description> <bash condition>
    if eval "$2"; then pass=$((pass + 1)); echo "PASS  $1"; else fail=$((fail + 1)); echo "FAIL  $1"; fi
}
finish() { echo; echo "passed: $pass   failed: $fail"; [ "$fail" = 0 ]; }
