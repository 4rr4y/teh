# Port 8768, OpenAI format: waits 3.5s before answering 'done' (thinking-timer tests)
import json, http.server, time
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["content-length"])); time.sleep(3.5)
        b = json.dumps({"model": "fake", "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "done"}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 1}}).encode()
        try: self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
        except (BrokenPipeError, ConnectionResetError): pass  # the client was cancelled (Ctrl+C test) and has gone
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8768), H).serve_forever()
