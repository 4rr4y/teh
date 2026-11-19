# Port 8765, OpenAI format: always replies with a tool call and a huge usage count (context-limit tests)
import json, http.server
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["content-length"]))
        r = {"model": "fake", "choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": "working",
             "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "bash", "arguments": "{\"command\": \"echo hi\"}"}}]}}],
             "usage": {"prompt_tokens": 1234567, "completion_tokens": 4321, "prompt_tokens_details": {"cached_tokens": 1000000}}}
        b = json.dumps(r).encode(); self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8765), H).serve_forever()
