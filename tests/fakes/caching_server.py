"""Port 8781, both formats: logs every request (path, headers and body) as one JSON line to argv[1], and answers with
one tool call, then text. The usage it reports depends on the URL path: /usage-deepseek/, /usage-header/ (a header,
as Fireworks reports it), /usage-top/, else OpenAI's."""
import json
import sys

from common import Handler, openai_reply, read_json, send_json, serve, text, tool_call

USAGES = {"/usage-deepseek/": {"prompt_tokens": 100, "completion_tokens": 1, "prompt_cache_hit_tokens": 77},
          "/usage-top/": {"prompt_tokens": 100, "completion_tokens": 1, "cached_tokens": 55},
          "/usage-header/": {"prompt_tokens": 100, "completion_tokens": 1}}
OPENAI_USAGE = {"prompt_tokens": 100, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 88}}

def tool_result(message):
    """Whether a message carries a tool's result, in either format."""
    content = message.get("content")
    return message.get("role") == "tool" or (isinstance(content, list) and content
                                             and content[0].get("type") == "tool_result")

class H(Handler):
    def do_POST(self):
        """Log the request; answer the first with a tool call, the next with "done"."""
        req = read_json(self)
        with open(sys.argv[1], "a") as log:
            log.write(json.dumps({"path": self.path, "headers": dict(self.headers), "body": req}) + "\n")
        first = not any(tool_result(m) for m in req["messages"])
        usage = next((u for part, u in USAGES.items() if part in self.path), OPENAI_USAGE)
        headers = {"fireworks-cached-prompt-tokens": "66"} if "/usage-header/" in self.path else {}
        if self.path.endswith("/messages"):
            content = ([{"type": "tool_use", "id": "t1", "name": "shell", "input": {"command": "echo hi"}}] if first
                       else [{"type": "text", "text": "done"}])
            reply = {"model": "fake", "stop_reason": "tool_use" if first else "end_turn", "content": content,
                     "usage": {"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 1}}
        else:
            reply = openai_reply(tool_call("echo hi") if first else text("done"), usage)
        send_json(self, reply, headers=headers)

serve(8781, H)
