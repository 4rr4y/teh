"""Port argv[1], OpenAI format: has teh run the commands in the file argv[2] (separated by lines of ---), one tool
call each, then answers "done". Logs each tool result to argv[3], as "=== result N:" and the result."""
import sys

from common import Handler, openai_reply, read_json, send_json, serve, text, tool_call

with open(sys.argv[2], encoding="utf-8") as script:
    COMMANDS = script.read().split("\n---\n")
LOG = sys.argv[3]

class H(Handler):
    def do_POST(self):
        """Log the last command's result, and call the next command (or answer "done")."""
        req = read_json(self)
        results = [m for m in req["messages"] if m["role"] == "tool"]
        if results and req["messages"][-1]["role"] == "tool":
            with open(LOG, "a", encoding="utf-8") as log:
                log.write(f"=== result {len(results)}:\n{results[-1]['content']}\n")
        n = len(results)
        send_json(self, openai_reply(tool_call(COMMANDS[n], f"c{n}") if n < len(COMMANDS) else text("done")))

serve(sys.argv[1], H)
