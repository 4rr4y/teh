# Port 8781, both formats.
# logs every request (headers + body) as one JSON line; answers with one tool call, then text.
# The usage block in the reply depends on the URL path: /usage-deepseek/, /usage-header/, /usage-top/, else OpenAI style.
import json, http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        open(sys.argv[1], "a").write(json.dumps({"path": self.path, "headers": dict(self.headers), "body": req}) + "\n")
        first = not any(m.get("role") == "tool" or isinstance(m.get("content"), list) and m["content"]
                        and m["content"][0].get("type") == "tool_result" for m in req["messages"])
        extra = {}
        if "/usage-deepseek/" in self.path: usage = {"prompt_tokens": 100, "completion_tokens": 1, "prompt_cache_hit_tokens": 77}
        elif "/usage-top/" in self.path: usage = {"prompt_tokens": 100, "completion_tokens": 1, "cached_tokens": 55}
        elif "/usage-header/" in self.path: usage = {"prompt_tokens": 100, "completion_tokens": 1}; extra = {"fireworks-cached-prompt-tokens": "66"}
        else: usage = {"prompt_tokens": 100, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 88}}
        if self.path.endswith("/messages"):
            content = ([{"type": "tool_use", "id": "t1", "name": "shell", "input": {"command": "echo hi"}}] if first
                       else [{"type": "text", "text": "done"}])
            r = {"model": "fake", "stop_reason": "tool_use" if first else "end_turn", "content": content,
                 "usage": {"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 1}}
        else:
            msg = ({"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                    "function": {"name": "shell", "arguments": "{\"command\": \"echo hi\"}"}}]} if first
                   else {"role": "assistant", "content": "done"})
            r = {"model": "fake", "choices": [{"finish_reason": "stop", "message": msg}], "usage": usage}
        b = json.dumps(r).encode()
        self.send_response(200); self.send_header("content-length", len(b))
        for k, v in extra.items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8781), H).serve_forever()
