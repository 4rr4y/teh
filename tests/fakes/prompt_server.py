"""Port argv[1], OpenAI format: answers with the prompt it got ("got: …", line breaks as " | "), so a test can see
what arrived, piped input included, and what comes back out of teh. No tool calls."""
import sys

from common import Handler, openai_reply, read_json, send_json, serve, text


class H(Handler):
    def do_POST(self):
        """Answer with the last message's text."""
        req = read_json(self)
        send_json(self, openai_reply(text("got: " + req["messages"][-1]["content"].replace("\n", " | "))))

serve(sys.argv[1], H)
