# teh's tests

```
tests/
  test_units.py   unit tests: plain Python, run on every system  (cd tests && python3 -m unittest test_units)
  fakes/          fake API servers on localhost, plain Python: shared by every system's suites
  unix/           Linux and macOS: bash suites, and a pseudo-terminal for chat  (tests/unix/run.sh)
  windows/        Windows: Python suites, for cmd and PowerShell  (python tests\windows\run.py)
```

No test needs an API key or the network: `teh` is pointed at a fake server (`TEH_BASE_URL=http://127.0.0.1:PORT`)
that answers with scripted replies and tool calls, and the suites check what `teh` printed, ran and sent.

## The Unix suites (`tests/unix/`)

`run.sh` runs the unit tests, then each `test_<suite>.sh`. `lib.sh` has what they share: `serve` starts a fake server
and waits until it accepts connections, `check` records a pass or a failure, `oneshot` runs `teh` once and returns its
exit code. `pty_run.py` drives chat in a pseudo-terminal, typing each input when `teh` shows a prompt. `inputs.py`
works out what each suite depends on, for `run.sh --changed`.

## The Windows suites (`tests/windows/`)

```
python tests\windows\run.py              every suite (about 40 seconds)
python tests\windows\run.py core fetch   some of them
python tests\windows\run.py --changed    only the suites affected by what changed since they last passed
```

Written in Python, so they need nothing but Python 3.10 or later: no bash, no extra packages. The suites have the
Unix suites' names (`units`, `core`, `chat`, `caching`, `errors`, `output`, `compact`, `fetch`) and cover the same
ground, plus what's Windows' own. GitHub Actions runs them on each push and pull request, on Windows with Python 3.10,
3.12 and 3.14.

- **`run.py`** runs the unit tests, then each `test_<suite>.py`; `--changed` works as on Unix, with `inputs.py`.
- **`lib.py`** has what the suites share: `Suite.serve` starts a fake server (and refuses a port already in use),
  `ready` waits until the servers accept connections, `teh` runs `teh` once and returns its exit code and output,
  `script` starts a fake model that has `teh` run a list of commands, `check` records a pass or a failure.
- **The shells:** the model's commands run in cmd and in Windows PowerShell, and in PowerShell 7 (`pwsh`) where it's
  installed (it is on GitHub's runners), each in its own syntax: quoting, exit codes, `teh-fetch` and `teh-edit` (a
  `.cmd` launcher in cmd, a function in PowerShell, with an `&` in an address), timeouts that stop a whole process
  tree, background jobs, the system prompt's advice for each shell, and which shell is picked without `TEH_SHELL`.
- **Chat:** there's no pseudo-terminal on Windows, so `chat_run.py` runs `teh` in its own process with the console
  replaced: input that says it's a terminal, and `msvcrt.kbhit` telling a paste from typed lines. It covers
  approvals, chat commands, chat input, the startup segment, `/clear` and `/compact`. The live thinking timer needs
  a real console, and isn't tested.
- **Ctrl+C:** Windows sends it to every process on a console, not to one, so `ctrl_c.py` runs `teh` in a hidden console
  of its own and presses Ctrl+C there (`output` suite).
- **No console:** a run started without one (a scheduled task, a service) is tested too (`output` suite).

**Known problems** are checked with `Suite.known` rather than `check`: they show as `KNOWN` with what's wrong, and
don't fail the suite, so the suites stay green while they're open. One that starts to pass says so; then make it a
`check`. None is open now: the three the suites found first (non-ASCII output in the console's code page, Windows
PowerShell's CLIXML on a redirected stderr, and helpers' exit codes lost in PowerShell) are fixed, and checked.
