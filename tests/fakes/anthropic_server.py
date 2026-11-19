"""Port 8779, Anthropic format: one tool_use, then the tool_result echoed back as text. Logs the request's shape (its
tools, cache marker and API version) to argv[2]."""
import json
import sys

from common import Handler, read_json, send_json, serve


class H(Handler):
    def do_POST(self):
        """Answer the first request with a tool call, the next with its result."""
        req = read_json(self)
        last = req["messages"][-1]
        if isinstance(last["content"], list) and last["content"][0].get("type") == "tool_result":
            content, stop = [{"type": "text", "text": "RESULT: " + last["content"][0]["content"].strip()}], "end_turn"
        else:
            with open(sys.argv[2], "w") as log:
                log.write(json.dumps({"tools": req["tools"], "cache_control": req.get("cache_control"),
                                      "version": self.headers.get("anthropic-version")}))
            command = {"command": "echo hi from anthropic"}
            content, stop = [{"type": "tool_use", "id": "t1", "name": "shell", "input": command}], "tool_use"
        send_json(self, {"model": "fake-claude", "stop_reason": stop, "content": content,
                         "usage": {"input_tokens": 5, "cache_read_input_tokens": 1000, "output_tokens": 2}})

serve(8779, H)
