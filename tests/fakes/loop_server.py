"""Port 8765, OpenAI format: always answers with a tool call and a huge usage count (context-limit tests)."""
from common import Handler, openai_reply, read_json, send_json, serve, tool_call

USAGE = {"prompt_tokens": 1234567, "completion_tokens": 4321, "prompt_tokens_details": {"cached_tokens": 1000000}}

class H(Handler):
    def do_POST(self):
        """Call the tool again, whatever the request."""
        read_json(self)
        message = {**tool_call("echo hi", name="bash"), "content": "working"}
        send_json(self, openai_reply(message, USAGE, finish_reason="tool_calls"))

serve(8765, H)
