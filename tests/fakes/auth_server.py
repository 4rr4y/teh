"""Port 8766, OpenAI format: logs the Authorization header to argv[1], and answers "ok"."""
import sys

from common import Handler, openai_reply, read_json, send_json, serve, text


class H(Handler):
    def do_POST(self):
        """Log the key, answer "ok"."""
        read_json(self)
        with open(sys.argv[1], "a") as log:
            log.write(f"auth={self.headers.get('authorization')}\n")
        send_json(self, openai_reply(text("ok")))

serve(8766, H)
