# teh's tests

```
tests/
  test_units.py   unit tests: plain Python, run on every system  (cd tests && python3 -m unittest test_units)
  fakes/          fake API servers on localhost, plain Python: shared by every system's suites
  unix/           Linux and macOS: bash suites, and a pseudo-terminal for chat  (tests/unix/run.sh)
```

No test needs an API key or the network: `teh` is pointed at a fake server (`TEH_BASE_URL=http://127.0.0.1:PORT`)
that answers with scripted replies and tool calls, and the suites check what `teh` printed, ran and sent.

## The Unix suites (`tests/unix/`)

`run.sh` runs the unit tests, then each `test_<suite>.sh`. `lib.sh` has what they share: `serve` starts a fake server
and waits until it accepts connections, `check` records a pass or a failure, `oneshot` runs `teh` once and returns its
exit code. `pty_run.py` drives chat in a pseudo-terminal, typing each input when `teh` shows a prompt. `inputs.py`
works out what each suite depends on, for `run.sh --changed`.

## Adding Windows suites (`tests/windows/`, not written yet)

What carries over unchanged: `test_units.py`, and every server in `fakes/` (plain Python; their scripted commands are
mostly `echo`, which PowerShell and cmd have too, but read each script: a few use `sleep` or Unix paths).

What needs writing, in PowerShell (`run.ps1`, `test_<suite>.ps1`), suite by suite after the Unix ones:

- **`serve` and `check`:** start a fake server in the background (`Start-Process python -ArgumentList ...`), wait for
  its port, stop it at the end; count passes and failures.
- **Commands as the model runs them:** `teh` runs the model's commands in PowerShell (or cmd) on Windows, with
  `teh-fetch` and `teh-edit` as functions (PowerShell) or `.cmd` launchers (cmd). The Windows suites are where these
  paths get tested for the first time: quoting (an address with `&`), UTF-8 output, `Start-Job` in the parallel advice.
- **Chat:** `pty_run.py` needs a Unix pseudo-terminal. On Windows, start with the one-shot suites (`core`, `output`,
  `errors`, `caching`, `compact`, `fetch`); chat needs a console driver (e.g. the `pywinpty` package) or a test of the
  chat loop through its functions instead.
- **Signals:** Windows has no SIGHUP; the scratch folder cleanup on closing the console is the case to test there.

Keep the suites' names, so `units`, `core`, `chat` and so on mean the same tests on every system.
