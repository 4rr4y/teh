# Port 8766, OpenAI format: logs the Authorization header to argv[1], replies 'ok'
import json, http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["content-length"]))
        open(sys.argv[1], "a").write(f"auth={self.headers.get('authorization')}\n")
        b = json.dumps({"model": "fake", "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 1}}).encode()
        self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8766), H).serve_forever()
