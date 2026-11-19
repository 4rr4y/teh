"""usage: chat_run.py INPUT ...: runs teh's chat with these inputs typed at its prompts, and prints all it showed, each
input marked as <<input>>. Works on every system (pty_run.py, on Unix only, uses a real pseudo-terminal instead).

teh runs in this process, with its terminal input replaced: sys.stdin says it's a terminal and gives one input per line
it's asked for, and teh.pasted_more (how teh tells a paste from typing) says more is waiting while an input has lines
left. So an input with several lines ("a\\nb") arrives as a paste, and separate inputs as typed lines. After the last
input, the terminal says end of file (Ctrl+D, or Ctrl+Z then Enter), which exits chat. Escapes as in Python ("\\n")."""
import sys
from pathlib import Path


class Console:
    """What teh reads from: a terminal, as far as it can tell."""
    def __init__(self, inputs):
        self.inputs = [item.encode().decode("unicode_escape") for item in inputs]
        # Lines left of the input being typed (a paste: several)
        self.lines = []

    def isatty(self):
        """Say it's a terminal, so teh starts a chat."""
        return True

    def readline(self):
        """Return the next line of the input being typed, or the next input; "" (end of file) after the last."""
        if not self.lines:
            if not self.inputs:
                # End of file: input() raises EOFError
                return ""
            item = self.inputs.pop(0)
            print(f"<<{item!r}>>", flush=True)
            self.lines = item.split("\n")
            if self.lines[-1] == "":
                self.lines.pop()
            self.lines = self.lines or [""]
        return self.lines.pop(0) + "\n"

    def waiting(self):
        """Whether more of a paste is already here."""
        return bool(self.lines)

    def reconfigure(self, **kwargs):
        """Accept teh's stream settings (there's nothing to set)."""

console = Console(sys.argv[1:])
sys.stdin = console
# No task: chat
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import teh

teh.pasted_more = console.waiting

sys.exit(teh.main())
