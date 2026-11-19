# Port 8767, OpenAI format.
# replies with one tool call running CMD, then echoes the tool result back as the answer; logs the system prompt
import json, http.server, sys
CMD = sys.argv[1]
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        last = req["messages"][-1]
        if last["role"] == "tool":
            msg = {"role": "assistant", "content": "RESULT: " + last["content"].strip()}
        else:
            open(sys.argv[2], "w", encoding="utf-8").write(req["messages"][0]["content"] + "\nTOOL: " + json.dumps(req["tools"][0]["function"]))
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                   "function": {"name": "shell", "arguments": json.dumps({"command": CMD})}}]}
        b = json.dumps({"model": "fake", "choices": [{"finish_reason": "stop", "message": msg}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 1}}).encode()
        self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8767), H).serve_forever()
