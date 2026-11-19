"""Port argv[1]: the first request is refused, later ones answered; logs the roles sent each time to argv[2]. argv[3]
picks the kind of refusal: anthropic, refusal (OpenAI's field) or filter (a content filter)."""
import sys

from common import Handler, openai_reply, read_json, send_json, serve, text

MODE = sys.argv[3]
REFUSAL = {"type": "refusal", "category": "cyber", "explanation": "This looks like malware development."}
# Requests so far
count = 0

class H(Handler):
    def do_POST(self):
        """Refuse the first request, in the chosen way; answer the rest."""
        global count
        count += 1
        req = read_json(self)
        with open(sys.argv[2], "a") as log:
            log.write(f"request {count} roles: {[m['role'] for m in req['messages']]}\n")
        if self.path.endswith("/messages"):
            if count == 1:
                reply = {"model": "fake", "stop_reason": "refusal", "content": [], "stop_details": REFUSAL,
                         "usage": {"input_tokens": 10, "output_tokens": 0}}
            else:
                reply = {"model": "fake", "stop_reason": "end_turn", "content": [{"type": "text", "text": "answered"}],
                         "usage": {"input_tokens": 10, "output_tokens": 1}}
        else:
            msg = {**text(None), "refusal": "I can't help with that."} if MODE == "refusal" else text("")
            reply = openai_reply(msg, {"prompt_tokens": 10, "completion_tokens": 0},
                                 finish_reason="content_filter" if MODE == "filter" else "stop")
        send_json(self, reply)

serve(sys.argv[1], H)
