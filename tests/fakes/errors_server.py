# Port 8782, OpenAI format.
# /cut/ : a reply cut off at max_tokens (finish_reason length)   /400/ : an HTTP 400 error
# /bad/<args>/ : one tool call with those raw arguments, then echo the tool result back as the answer
# /429/<header>=<value>/ : first request gets 429 with that header, then a normal answer
import json, http.server, sys, urllib.parse
seen = set()
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        parts = self.path.split("/")
        if parts[1] == "429" and self.path not in seen:
            seen.add(self.path)
            name, value = urllib.parse.unquote(parts[2]).split("=")
            self.send_response(429)
            if name != "none": self.send_header(name, value)
            self.send_header("content-length", "2"); self.end_headers(); self.wfile.write(b"{}"); return
        if parts[1] == "400":
            b = b'{"error": "bad thing"}'
            self.send_response(400); self.send_header("content-length", len(b)); self.end_headers()
            self.wfile.write(b); return
        if parts[1] == "cut":
            b = json.dumps({"model": "fake", "choices": [{"finish_reason": "length", "message": {"role": "assistant",
                            "content": "partial answ"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
            self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
            return
        last = req["messages"][-1]
        if parts[1] == "bad" and last["role"] != "tool":
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                   "function": {"name": "shell", "arguments": urllib.parse.unquote(parts[2])}}]}
        else:
            msg = {"role": "assistant", "content": "RESULT: " + (last["content"] if last["role"] == "tool" else "ok")}
        b = json.dumps({"model": "fake", "choices": [{"finish_reason": "stop", "message": msg}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 1}}).encode()
        self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8782), H).serve_forever()
