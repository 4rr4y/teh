"""Port 8782, OpenAI format: errors, chosen by the URL path.
  /cut/                   a reply cut off at max_tokens (finish_reason length)
  /400/                   an HTTP 400 error
  /bad/<args>/            one tool call with those raw arguments, then the tool's result echoed back as the answer
  /429/<header>=<value>/  the first request gets a 429 with that header (none=x: no header), then a normal answer"""
import urllib.parse

from common import Handler, openai_reply, read_json, send_json, serve, text

# The 429 paths already answered with a 429
seen = set()

class H(Handler):
    def do_POST(self):
        """Answer as the path says (see the module's docstring)."""
        req = read_json(self)
        parts = self.path.split("/")
        if parts[1] == "429" and self.path not in seen:
            seen.add(self.path)
            name, value = urllib.parse.unquote(parts[2]).split("=")
            send_json(self, b"{}", 429, {name: value} if name != "none" else {})
            return
        if parts[1] == "400":
            send_json(self, b'{"error": "bad thing"}', 400)
            return
        if parts[1] == "cut":
            send_json(self, openai_reply(text("partial answ"), {"prompt_tokens": 10, "completion_tokens": 5},
                                         finish_reason="length"))
            return
        last = req["messages"][-1]
        if parts[1] == "bad" and last["role"] != "tool":
            raw = urllib.parse.unquote(parts[2])
            msg = {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "shell", "arguments": raw}}]}
        else:
            msg = text("RESULT: " + (last["content"] if last["role"] == "tool" else "ok"))
        send_json(self, openai_reply(msg))

serve(8782, H)
