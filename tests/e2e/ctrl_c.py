"""usage: ctrl_c.py SECONDS teh.py ARG ...: runs teh, presses Ctrl+C after SECONDS, prints teh's exit code.

Windows has no SIGINT to send to one process: Ctrl+C is an event for every process attached to a console. So this
script is started in a console of its own (lib.py: Suite.ctrl_c), runs teh in it, and sends the event to that whole
console, ignoring it itself. teh, like in a real console, gets KeyboardInterrupt."""
import ctypes
import signal
import subprocess
import sys
import time

ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)  # make sure Ctrl+C isn't ignored by what this starts
signal.signal(signal.SIGINT, signal.SIG_IGN)               # but this script itself carries on
p = subprocess.Popen([sys.executable, "-B", *sys.argv[2:]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(float(sys.argv[1]))
ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, 0)  # CTRL_C_EVENT, to every process on this console
try:
    code = p.wait(timeout=20)
except subprocess.TimeoutExpired:
    p.kill()
    code = "hung"
print(code, flush=True)
