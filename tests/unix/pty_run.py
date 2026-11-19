# usage: pty_run.py <script> <input1> <input2> ...: runs the script in a pseudo-terminal and types each input once it
# shows a new prompt ("> ", "… " or the approval question), not after a fixed wait; \x04 etc. allowed. Prints all
# it showed, with each input marked as <<input>>.
import os, pty, select, sys, time

PROMPTS = (b">", "…".encode(), b"instead:")  # how a prompt ends (trailing spaces aside)
pid, fd = pty.fork()
if pid == 0:
    os.execvp("python3", ["python3", "-B", sys.argv[1]])
out = b""

def read(timeout):  # add what arrives within timeout seconds to out -> False once the program has exited
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

QUIET = 0.15  # a prompt counts once nothing more has been shown for this long: while teh reads a paste, it shows
              # "… " between the pasted lines within milliseconds, and the next input mustn't go in among them

mark = 0  # where the output since the last input starts: a prompt counts only if it comes after it
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
while read(1):  # the rest, until it exits
    pass
print(out.decode(errors="replace").replace("\r", ""))
