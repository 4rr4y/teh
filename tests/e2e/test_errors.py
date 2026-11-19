"""Error handling: malformed tool calls are answered instead of ending the turn; retries honour retry-after."""
import urllib.parse

from lib import DEFAULT_SHELL, Suite, section

s = Suite()
s.serve("errors_server.py")
s.ready()
U = "http://127.0.0.1:8782"
def enc(text):
    """Return text quoted for a URL path."""
    return urllib.parse.quote(text, safe="")

section("malformed tool calls")
for args, expect in [("{not json", "not valid JSON"), ("{}", "no command was given"), ("[1,2]", "not a JSON object"),
                     ('{"command": "   "}', "no command was given")]:
    r = s.teh("go", env={"TEH_BASE_URL": f"{U}/bad/{enc(args)}", "TEH_MODEL": "m", "TEH_AUTO": 1,
                         "TEH_SHELL": DEFAULT_SHELL})
    s.check(f"arguments {args}: turn continues, model told '{expect}'",
            r.code == 0 and "RESULT: Not run: " in r.both and expect in r.both)

section("retry-after")
for header, shown, secs in [("retry-after=1", "1s", 1.0), ("retry-after-ms=1500", "1.5s", 1.5), ("none=x", "2s", 2.0)]:
    r = s.teh("go", env={"TEH_BASE_URL": f"{U}/429/{enc(header)}/v1", "TEH_MODEL": "m"})
    # teh's own start-up (Python, the shell lookup) is part of the time measured here, so allow it a little more
    s.check(f"{header}: 'retrying in {shown}', waited ~{secs}s (took {r.seconds:.1f}s)",
            f"retrying in {shown}" in r.err and secs <= r.seconds < secs + 2.5)

s.finish()
