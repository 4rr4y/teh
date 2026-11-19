# Port 8786, OpenAI format: a conversation that fills a 1,000-token window, for compaction tests. Logs each request
# (one JSON line) to argv[1]. A /fail/ in the URL path makes the summary request fail with HTTP 400.
#   no command run yet          -> a tool call (echo hi), reporting 1,005 tokens used: the window is full
#   a command has run           -> "done"
#   the summary request         -> "SUMMARY-TEXT" (and the server copies the transcript teh saved into the log)
#   a compacted conversation    -> "continued after compaction"
import json, http.server, re, sys
LOG = sys.argv[1]

class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        msgs = req["messages"]
        with open(LOG, "a") as f:
            f.write(json.dumps({"path": self.path, "body": req}) + "\n")
        last, first = msgs[-1], msgs[1]  # msgs[0] is the system prompt
        usage = {"prompt_tokens": 100, "completion_tokens": 5}
        if last["role"] == "user" and "about to be compacted" in (last["content"] or ""):
            if "/fail/" in self.path:
                self.send_response(400); self.send_header("content-length", "2"); self.end_headers()
                self.wfile.write(b"{}"); return
            msg = {"role": "assistant", "content": "SUMMARY-TEXT"}
        elif str(first["content"]).startswith("[This conversation was compacted"):
            path = re.search(r"saved at (\S+?): grep", first["content"]).group(1)
            with open(LOG, "a") as f:
                f.write(json.dumps({"transcript": open(path, encoding="utf-8").read()}) + "\n")
            msg = {"role": "assistant", "content": "continued after compaction"}
        elif not any(m["role"] == "tool" for m in msgs):
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                   "function": {"name": "shell", "arguments": json.dumps({"command": "echo hi"})}}]}
            usage = {"prompt_tokens": 995, "completion_tokens": 10}
        else:
            msg = {"role": "assistant", "content": "done"}
        b = json.dumps({"model": "fake", "choices": [{"finish_reason": "stop", "message": msg}], "usage": usage}).encode()
        self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass

http.server.HTTPServer(("127.0.0.1", 8786), H).serve_forever()
