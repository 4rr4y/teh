# Port argv[1]: a fake web API for the web helper's request options. Any method, any path: answers with what it got,
# as JSON (method, path, headers, body). /bad answers HTTP 400 with a JSON explanation, /page-error 403 with HTML.
# Misbehaving answers, for the helper's error handling: /truncated promises 1,000 bytes and sends 10, /bomb is 60 KB
# of gzip that unpacks to 60 MB, /corrupt-gzip starts like gzip and isn't, /badcharset names a charset that doesn't exist.
import gzip, json, http.server, sys
BOMB = gzip.compress(b"0" * 60_000_000)
class H(http.server.BaseHTTPRequestHandler):
    def answer(self):
        body = self.rfile.read(int(self.headers.get("content-length") or 0)).decode()
        code, kind, length = 200, "application/json", None
        if self.path == "/bad":
            code, out = 400, json.dumps({"error": "missing field: name"}).encode()
        elif self.path == "/page-error":
            code, kind, out = 403, "text/html", ("<html><body>" + "<p>FORBIDDEN_PAGE</p>" * 50 + "</body></html>").encode()
        elif self.path == "/truncated":
            kind, out, length = "text/plain", b"0123456789", 1000
        elif self.path == "/bomb":
            kind, out = "text/plain", BOMB
        elif self.path == "/corrupt-gzip":
            kind, out = "text/plain", b"\x1f\x8b\x08\x00" + b"not gzip at all" * 10
        elif self.path == "/badcharset":
            kind, out = "text/plain; charset=no-such-charset", "café BADCHARSET_TEXT".encode()
        else:
            out = json.dumps({"method": self.command, "path": self.path, "body": body,
                              "headers": {k.lower(): v for k, v in self.headers.items()}}).encode()
        self.send_response(code); self.send_header("content-type", kind)
        self.send_header("content-length", length or len(out)); self.end_headers()
        try:
            self.wfile.write(out)
        except (BrokenPipeError, ConnectionResetError):  # the client stopped reading (the gzip bomb): fine
            pass
    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = answer
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
