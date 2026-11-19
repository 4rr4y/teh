"""Port 8767, OpenAI format: one tool call running the command argv[1], then the tool's result echoed back as the
answer. Logs the system prompt and the tool's definition to argv[2]."""
import json
import sys

from common import Handler, openai_reply, read_json, send_json, serve, text, tool_call

COMMAND = sys.argv[1]

class H(Handler):
    def do_POST(self):
        """Answer the first request with the tool call, the next with its result."""
        req = read_json(self)
        last = req["messages"][-1]
        if last["role"] == "tool":
            msg = text("RESULT: " + last["content"].strip())
        else:
            with open(sys.argv[2], "w", encoding="utf-8") as log:
                log.write(req["messages"][0]["content"] + "\nTOOL: " + json.dumps(req["tools"][0]["function"]))
            msg = tool_call(COMMAND)
        send_json(self, openai_reply(msg))

serve(8767, H)
