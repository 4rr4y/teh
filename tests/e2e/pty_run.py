"""usage: pty_run.py SCRIPT INPUT ...: runs the script in a pseudo-terminal and types each input once it shows a new
prompt ("> ", "… " or the approval question), not after a fixed wait; \\x04 etc. allowed. Prints all it showed, with
each input marked as <<input>>.

Unix only: for what needs a real terminal, such as bracketed paste and Ctrl+D. chat_run.py works everywhere."""
import os
import pty
import select
import sys
import time

# How a prompt ends (trailing spaces aside)
PROMPTS = (b">", "…".encode(), b"instead:")
pid, fd = pty.fork()
if pid == 0:
    os.execv(sys.executable, [sys.executable, "-B", sys.argv[1]])
out = b""

def read(timeout):
    """Add what arrives within timeout seconds to out; return False once the program has exited."""
    global out
    if select.select([fd], [], [], timeout)[0]:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            return False
        if not chunk:
            return False
        out += chunk
    return True

# A prompt counts once nothing more has been shown for this long: while teh reads a paste, it shows "… " between the
# pasted lines within milliseconds, and the next input mustn't go in among them
QUIET = 0.15

# Where the output since the last input starts: a prompt counts only if it comes after it
mark = 0
for item in sys.argv[2:]:
    end = time.time() + 10
    shown, changed = len(out), time.time()
    while time.time() < end and read(0.05):
        if len(out) != shown:
            shown, changed = len(out), time.time()
        elif out[mark:].rstrip().endswith(PROMPTS) and time.time() - changed >= QUIET:
            break
    os.write(fd, item.encode().decode("unicode_escape").encode())
    out += b"<<" + item.encode() + b">>"
    mark = len(out)
# The rest, until it exits
while read(1):
    pass
print(out.decode(errors="replace").replace("\r", ""))
