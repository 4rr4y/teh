# teh's tests

```
tests/
  test_units.py   unit tests  (cd tests && python -m unittest test_units)
  fakes/          fake API servers on localhost (what they share is in common.py)
  e2e/            the suites: teh run as people and scripts run it  (python tests/e2e/run.py)
```

No test needs an API key or the network: `teh` is pointed at a fake server (`TEH_BASE_URL=http://127.0.0.1:PORT`)
that answers with scripted replies and tool calls, and the suites check what `teh` printed, ran and sent.

Everything is plain Python 3.10 or later, with no extra packages, and the same suites run on Linux, macOS and Windows.
GitHub Actions runs them on each push and pull request, on Linux and on Windows, with Python 3.10, 3.12 and 3.14.

## The suites (`tests/e2e/`)

```
python tests/e2e/run.py              every suite (about a minute)
python tests/e2e/run.py core fetch   some of them
python tests/e2e/run.py --changed    only the suites affected by what changed since they last passed
```

The suites are `units`, `core`, `chat`, `caching`, `errors`, `output`, `compact` and `fetch` (what each covers is in
[DESIGN.md](../DESIGN.md#tests)).

- **`run.py`** runs the unit tests, then each `test_<suite>.py`; `--changed` uses `inputs.py`, which works out what
  each suite depends on.
- **`lib.py`** has what the suites share, and everything that differs between systems, so a suite says what it checks
  once:
  - `SHELLS`: the shells to run the model's commands in. bash and sh (and zsh where it's installed); on Windows cmd and
    Windows PowerShell (and PowerShell 7, `pwsh`, where it's installed, as on GitHub's runners). `family()` says which
    syntax a shell uses, and a suite gives each scenario in each syntax: quoting, exit codes, `teh-fetch` and
    `teh-edit` (a `.cmd` launcher in cmd, a function in PowerShell, a launcher on the `PATH` elsewhere), timeouts that
    stop a whole process tree, background jobs, the system prompt's advice for each shell, and which shell is picked
    without `TEH_SHELL`.
  - `Suite.serve` starts a fake server (and refuses a port already in use), `ready` waits until the servers accept
    connections, `teh` runs `teh` once and returns its exit code and output, `script` starts a fake model that has `teh`
    run a list of commands, `check` records a pass or a failure.
  - `Suite.ctrl_c` presses Ctrl+C: a SIGINT on Unix; on Windows, where Ctrl+C goes to every process on a console,
    `ctrl_c.py` runs `teh` in a hidden console of its own and presses it there.
  - `Suite.teh(detached=True)` runs `teh` without a terminal or console, as cron, a scheduled task or a service would.
  - `Suite.processes` lists the running processes, to check that a timed-out command was stopped and a background job
    wasn't.
- **Chat:** `chat_run.py` runs `teh`'s chat on any system with its terminal input replaced: input that says it's a
  terminal, and `teh.pasted_more` telling a paste from typed lines. It covers approvals, chat commands, chat input,
  the startup segment, `/clear` and `/compact`. On Unix, `pty_run.py` and the chat suite also run `teh` in a real
  pseudo-terminal, for what needs one: the terminal's paste markers, Ctrl+C during a command, the live thinking timer,
  colour, and SIGHUP and SIGTERM.

**Known problems** are checked with `Suite.known` rather than `check`: they show as `KNOWN` with what's wrong, and
don't fail the suite, so the suites stay green while they're open. One that starts to pass says so; then make it a
`check`. None is open now.
