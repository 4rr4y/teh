"""Port 8786, OpenAI format: a conversation that fills a 1,000-token window, for compaction tests. Logs each request
(one JSON line) to argv[1]. A /fail/ in the URL path makes the summary request fail with HTTP 400.
  no command run yet          -> a tool call (echo hi), reporting 1,005 tokens used: the window is full
  a command has run           -> "done"
  the summary request         -> "SUMMARY-TEXT" (and the server copies the transcript teh saved into the log)
  a compacted conversation    -> "continued after compaction"
"""
import json
import re
import sys

from common import Handler, openai_reply, read_json, send_json, serve, text, tool_call

LOG = sys.argv[1]

def log(entry):
    """Add one JSON line to the log."""
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

class H(Handler):
    def do_POST(self):
        """Answer as the conversation's stage says (see the module's docstring)."""
        req = read_json(self)
        msgs = req["messages"]
        log({"path": self.path, "body": req})
        # msgs[0] is the system prompt
        last, first = msgs[-1], msgs[1]
        usage = {"prompt_tokens": 100, "completion_tokens": 5}
        if last["role"] == "user" and "about to be compacted" in (last["content"] or ""):
            if "/fail/" in self.path:
                send_json(self, b"{}", 400)
                return
            msg = text("SUMMARY-TEXT")
        elif str(first["content"]).startswith("[This conversation was compacted"):
            path = re.search(r"saved at (\S+?): grep", first["content"]).group(1)
            with open(path, encoding="utf-8") as transcript:
                log({"transcript": transcript.read()})
            msg = text("continued after compaction")
        elif not any(m["role"] == "tool" for m in msgs):
            msg, usage = tool_call("echo hi"), {"prompt_tokens": 995, "completion_tokens": 10}
        else:
            msg = text("done")
        send_json(self, openai_reply(msg, usage))

serve(8786, H)
