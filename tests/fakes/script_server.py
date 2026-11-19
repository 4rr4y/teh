# Port argv[1], OpenAI format.
# OpenAI-format fake: issues the commands in argv[2] (one per line) as tool calls, logs each tool result to argv[3]
import json, http.server, sys
cmds = open(sys.argv[2], encoding="utf-8").read().split("\n---\n")
log = sys.argv[3]
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        tool_msgs = [m for m in req["messages"] if m["role"] == "tool"]
        if tool_msgs and req["messages"][-1]["role"] == "tool":
            open(log, "a", encoding="utf-8").write(f"=== result {len(tool_msgs)}:\n{tool_msgs[-1]['content']}\n")
        n = len(tool_msgs)
        if n < len(cmds):
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": f"c{n}", "type": "function",
                   "function": {"name": "shell", "arguments": json.dumps({"command": cmds[n]})}}]}
        else:
            msg = {"role": "assistant", "content": "done"}
        b = json.dumps({"model": "fake", "choices": [{"finish_reason": "stop", "message": msg}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 1}}).encode()
        self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
