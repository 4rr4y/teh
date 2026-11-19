# Port 8779, Anthropic format.
# Anthropic-format fake: one tool_use, then echoes the tool_result back as text; logs the request shape
import json, http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        last = req["messages"][-1]
        if isinstance(last["content"], list) and last["content"][0].get("type") == "tool_result":
            content = [{"type": "text", "text": "RESULT: " + last["content"][0]["content"].strip()}]; stop = "end_turn"
        else:
            open(sys.argv[2], "w").write(json.dumps({"tools": req["tools"], "cache_control": req.get("cache_control"),
                "version": self.headers.get("anthropic-version")}))
            content = [{"type": "tool_use", "id": "t1", "name": "shell", "input": {"command": "echo hi from anthropic"}}]; stop = "tool_use"
        b = json.dumps({"model": "fake-claude", "stop_reason": stop, "content": content,
                        "usage": {"input_tokens": 5, "cache_read_input_tokens": 1000, "output_tokens": 2}}).encode()
        self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8779), H).serve_forever()
