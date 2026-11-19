"""Port 8768, OpenAI format: waits 3.5s, then answers "done" (thinking timer and Ctrl+C tests)."""
import time

from common import Handler, openai_reply, read_json, send_json, serve, text


class H(Handler):
    def do_POST(self):
        """Answer "done", slowly."""
        read_json(self)
        time.sleep(3.5)
        try:
            send_json(self, openai_reply(text("done")))
        except (BrokenPipeError, ConnectionResetError):
            # The client was cancelled (the Ctrl+C test) and has gone
            pass

serve(8768, H)
