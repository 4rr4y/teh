"""usage: chat_run.py INPUT ...: runs teh's chat with these inputs typed at its prompts, and prints all it showed, each
input marked as <<input>>. The Windows counterpart of tests/unix/pty_run.py, which needs a Unix pseudo-terminal.

teh runs in this process, with its console input replaced: sys.stdin says it's a terminal and gives one input per line
it's asked for, and msvcrt.kbhit (how teh tells a paste from typing on Windows) says more is waiting while an input has
lines left. So an input with several lines ("a\\nb") arrives as a paste, and separate inputs as typed lines. After the
last input, the console says end of file: Ctrl+Z, Enter, which exits chat. Escapes as in Python ("\\n")."""
import msvcrt, sys
from pathlib import Path

class Console:  # what teh reads from: a terminal, as far as it can tell
    def __init__(self, inputs):
        self.inputs = [item.encode().decode("unicode_escape") for item in inputs]
        self.lines = []  # lines left of the input being typed (a paste: several)

    def isatty(self):
        return True

    def readline(self):
        if not self.lines:
            if not self.inputs:
                return ""  # end of file: input() raises EOFError
            item = self.inputs.pop(0)
            print(f"<<{item!r}>>", flush=True)
            self.lines = item.split("\n")
            if self.lines[-1] == "":
                self.lines.pop()
            self.lines = self.lines or [""]
        return self.lines.pop(0) + "\n"

    def waiting(self):  # more of a paste is already here
        return bool(self.lines)

    def reconfigure(self, **kwargs):
        pass

console = Console(sys.argv[1:])
msvcrt.kbhit = console.waiting
sys.stdin = console
sys.argv = [sys.argv[0]]  # no task: chat
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import teh  # noqa: E402

sys.exit(teh.main())
