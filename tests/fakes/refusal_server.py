# Port argv[1]; argv[3] picks the kind of refusal: anthropic, refusal (OpenAI field) or filter.
# first request is refused, later ones answered; logs the roles sent each time
import json, http.server, sys
n = 0
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        global n; n += 1
        req = json.loads(self.rfile.read(int(self.headers["content-length"])))
        open(sys.argv[2], "a").write(f"request {n} roles: {[m['role'] for m in req['messages']]}\n")
        mode = sys.argv[3]
        if self.path.endswith("/messages"):
            r = ({"model": "fake", "stop_reason": "refusal", "content": [],
                  "stop_details": {"type": "refusal", "category": "cyber", "explanation": "This looks like malware development."},
                  "usage": {"input_tokens": 10, "output_tokens": 0}} if n == 1 else
                 {"model": "fake", "stop_reason": "end_turn", "content": [{"type": "text", "text": "answered"}],
                  "usage": {"input_tokens": 10, "output_tokens": 1}})
        else:
            msg = ({"role": "assistant", "content": None, "refusal": "I can't help with that."} if mode == "refusal"
                   else {"role": "assistant", "content": ""})
            r = {"model": "fake", "choices": [{"finish_reason": "content_filter" if mode == "filter" else "stop", "message": msg}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 0}}
        b = json.dumps(r).encode()
        self.send_response(200); self.send_header("content-length", len(b)); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
