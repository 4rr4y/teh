# Port argv[1], OpenAI format: answers with the prompt it got ("got: …", line breaks as " | "), so a test can see
# what arrived, piped input included, and what comes back out of teh. No tool calls.
import json, http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        text = "got: " + req["messages"][-1]["content"].replace("\n", " | ")
        b = json.dumps({"model": "fake", "choices": [{"finish_reason": "stop", "message": {"role": "assistant",
                        "content": text}}], "usage": {"prompt_tokens": 10, "completion_tokens": 1}}).encode()
        self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
