# teh

token efficient harness: a minimal LLM agent in one Python file, with no dependencies. The name is also a nod to Singapore's *teh*.

You give it a task; the model gets one tool, your shell, and runs commands until the task is done, asking you before each one. It works with Anthropic's API and any OpenAI-compatible API (about 30 providers built in), on Linux, macOS and Windows, and shows exactly how many tokens each reply costs.

## Why teh

Every model call resends the whole conversation, so `teh` is built to keep it small and cached:

- **One tool, one short prompt.** The shell is the only tool (about 50 tokens), and the system prompt (about 400) never changes, so the provider serves it from its cache on every call, and in the next session too.
- **Prompt caching switched on for you,** where a provider makes it opt-in, with session ids where a provider needs them, and cache hits counted on the status line.
- **Edits, not rewrites.** Files change through `teh-edit`, exact search-and-replace that forgives indentation slips and explains failures without another read, so a one-line fix costs a few lines of output.
- **Lean command output.** Colour codes, progress bars and repeats are removed, long output is cut with the full copy saved for `grep`, and a command run again shows only what changed.
- **The web, as excerpts.** `teh-fetch` turns pages into text, prints only the lines you're looking for, prefers sites' cleaner sources, and searches 20 free official APIs.
- **Long sessions that keep going.** When the context fills, the conversation is summarised from the cache, your requests kept word for word, and the work carries on.
- **You stay in control:** a status line with the cost of every reply, `/undo`, `/compact`, `/effort`, and token and call budgets.

How it all works, and why, is in [DESIGN.md](DESIGN.md).

## Quick start

All it needs is Python 3.10 or later. This starts a chat with DeepSeek V4.1 Flash through OpenCode Go, at high reasoning effort, running commands without asking (`TEH_AUTO=1`; leave it out to approve each one, see [Safety](#safety)) and without reading `AGENTS.md` files. Put your API key in place of `<your key>`.

Linux and macOS (sh, bash, zsh):

```sh
git clone https://github.com/4rr4y/teh && cd teh
export TEH_BASE_URL=opencode-go TEH_MODEL=deepseek-v4.1-flash TEH_EFFORT=high TEH_AUTO=1 TEH_AGENTS_MD=0
export TEH_API_KEY="<your key>"
python3 teh.py
```

Windows, Command Prompt (cmd):

```bat
git clone https://github.com/4rr4y/teh && cd teh
set "TEH_BASE_URL=opencode-go"
set "TEH_MODEL=deepseek-v4.1-flash"
set "TEH_EFFORT=high"
set "TEH_AUTO=1"
set "TEH_AGENTS_MD=0"
set "TEH_API_KEY=<your key>"
python teh.py
```

Windows, PowerShell (Windows PowerShell or PowerShell 7):

```powershell
git clone https://github.com/4rr4y/teh; cd teh
$env:TEH_BASE_URL = "opencode-go"; $env:TEH_MODEL = "deepseek-v4.1-flash"; $env:TEH_EFFORT = "high"
$env:TEH_AUTO = "1"; $env:TEH_AGENTS_MD = "0"
$env:TEH_API_KEY = "<your key>"
python teh.py
```

On Windows, `py teh.py` works too where the Python launcher is installed. The settings last until the terminal is closed. `TEH_BASE_URL` is a [provider name](#providers) or any API URL. All settings are environment variables; see [Settings](#settings).

### A `teh` command

To type `teh` instead of `python3 teh.py`, from any folder:

```sh
chmod +x teh.py && ln -s "$PWD/teh.py" ~/.local/bin/teh          # sh, bash, zsh: ~/.local/bin must be on PATH
```

```bat
rem cmd: a teh.cmd in a folder on PATH, here %USERPROFILE%\bin (run in the teh folder)
mkdir "%USERPROFILE%\bin" 2>nul & echo @python "%CD%\teh.py" %*> "%USERPROFILE%\bin\teh.cmd"
```

```powershell
# PowerShell: a function in your profile, loaded by every new PowerShell window (run in the teh folder)
New-Item -ItemType Directory -Force (Split-Path $PROFILE) | Out-Null
Add-Content $PROFILE '$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false'
$line = 'function teh { $in = @($input); if ($in.Count) { $in | python "TEH" $args } else { python "TEH" $args } }'
Add-Content $PROFILE $line.Replace("TEH", "$PWD\teh.py")
```

In PowerShell, the function passes on what's piped to it (`git diff | teh "review this"`) only when there is something, so `teh` on its own still chats in the console. The first line makes text piped to and from programs UTF-8, so non-English text survives `git diff | teh` and `teh … | Set-Content` (Windows PowerShell's defaults are ASCII and the console's old code page; PowerShell 7's still the latter). It works in every version, 1.0 to 7. Windows PowerShell doesn't load profiles until scripts are allowed for your user: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Without the profile, run these lines in each new window instead.

The examples below use `teh`; without the command, use `python3 teh.py` (sh) or `python teh.py` (Windows) instead.

## Interactive use

```
$ teh
teh · startup
  os       Linux 6.8.0 (x86_64)
  shell    bash (/bin/bash)
  …
  keys     Ctrl+C cancels the current turn · Ctrl+D exits

> why does make fail?
· claude-opus-5-5 · default · 2.8s · in 2,301 · out 64 · Σ 2,365 · ctx 2,365/262,144 (1%)

$ make 2>&1 | tail -15
run? [y]es · [a]ll · [N]o, or type what to do instead: y

The linker can't find libssl. Install it with `sudo apt install libssl-dev`, then run make again.
· claude-opus-5-5 · default · 3.4s · in 2,980 (2,301 cached) · out 41 · Σ 5,386 (2,301 cached) · ctx 3,021/262,144 (1%)

>
```

Things to try at the prompt:

```
> find the slowest test in this project
> summarise https://docs.python.org/3/whatsnew/3.14.html            # web pages: read through the helper
> (paste an error log or a code snippet)                            # a pasted block is one prompt
> rename all .jpeg files here to .jpg \                             # end a line with \ to keep typing
  and lower-case their names
> /effort low                                                       # cheaper, quicker replies
> /compact keep the API changes                                     # summarise a long conversation, and go on
> /undo                                                             # drop the last prompt and what it led to
> /budget tokens 2000000                                            # change a budget mid-chat (0 = no limit)
> /clear                                                            # start a new conversation
```

When a command is shown for approval: `y` runs it, `a` runs it and every later one, Enter declines, and **any other text declines and tells the model what to do instead**, e.g. `use rg instead of grep -r`. Ctrl+C stops the model mid-turn; commands that already finished stay in the conversation, so you can say `continue`. Ctrl+D exits (on Windows: Ctrl+Z, then Enter), as does Ctrl+C at an empty prompt.

## Scripts and pipelines

With a task (or piped input), `teh` runs once and exits. The answer, the model's last reply, goes to stdout at the end; its earlier replies, status lines and commands go to stderr, so pipes get only the answer. Piped input is added to the task, cleaned of terminal codes; very long input is cut to fit, with the whole of it saved for the model to `grep`.

sh, bash, zsh:

```sh
teh "what's using the most disk space here?"                    # one question, one answer
git diff | teh "review this change"                             # piped input, plus a task
git diff --staged | teh "write a commit message" > msg.txt      # the answer, into a file
cat error.log | teh "explain this error" | less
teh "list the TODOs in this repo as a Markdown checklist" | tee TODO.md
teh "summarise this file in 3 lines" < notes.txt                # a file as input
TEH_AUTO=1 teh "run the tests and fix any failures"             # no approval prompts, for this run only
```

cmd:

```bat
teh "what's using the most disk space here?"
git diff | teh "review this change"
git diff --staged | teh "write a commit message" > msg.txt
type error.log | teh "explain this error" | more
teh "summarise this file in 3 lines" < notes.txt
set "TEH_AUTO=1" & teh "run the tests and fix any failures" & set "TEH_AUTO="
```

PowerShell, with the `teh` function and the UTF-8 line from [A `teh` command](#a-teh-command) (these work in Windows PowerShell 5.1 and PowerShell 7; avoid `"` inside a prompt, which Windows PowerShell drops from a program's arguments, a bug fixed in PowerShell 7.3):

```powershell
teh "what's using the most disk space here?"
git diff | teh "review this change"
git diff --staged | teh "write a commit message" | Set-Content msg.txt    # > writes UTF-16 in Windows PowerShell
Get-Content -Encoding UTF8 error.log | teh "explain this error" | more
teh "list the TODOs in this repo as a Markdown checklist" | Tee-Object -Variable todo; $todo | Set-Content TODO.md
Get-Content -Encoding UTF8 notes.txt | teh "summarise this file in 3 lines"   # PowerShell has no < for input
$env:TEH_AUTO = "1"; teh "run the tests and fix any failures"; Remove-Item env:TEH_AUTO
```

Windows PowerShell's `Get-Content` reads a file without a byte-order mark in the ANSI code page, so `-Encoding UTF8` keeps UTF-8 files' non-English text whole (PowerShell 7 reads UTF-8 by default). Its `Set-Content` writes the ANSI code page; add `-Encoding UTF8` for UTF-8 there too.

**No terminal** (CI, cron, a scheduled task, a script run in the background): set `TEH_AUTO=1`. There's nobody to approve commands, so without it the run stops with `no terminal to approve commands: set TEH_AUTO=1` (exit code 1).

The **exit code** says how the run ended (1 error, 2 refused, 3 context full, 4 cut off, 5 budget, 130 cancelled), and `TEH_OUTPUT=json` prints the whole result as one JSON object. The settings below are set for the rest of the session in cmd and PowerShell, as they have no way to set one for a single command.

```sh
if TEH_AUTO=1 teh "check that the docs build without warnings" > report.txt; then
    echo "ok"
else
    echo "teh ended with exit code $?"
fi

TEH_OUTPUT=json TEH_AUTO=1 teh "how many Python files are here?" | jq -r .answer
TEH_OUTPUT=json TEH_AUTO=1 teh "update the changelog" | jq '.tokens, .commands'

for f in src/*.py; do                             # one run per file
    teh "suggest one improvement to this file" < "$f" > "reviews/$(basename "$f").md"
done
```

```bat
set "TEH_AUTO=1"
call teh "check that the docs build without warnings" > report.txt
if errorlevel 1 (echo teh ended with exit code %errorlevel%) else (echo ok)

rem one run per file (in a .cmd file, write %%f instead of %f)
for %f in (src\*.py) do @teh "suggest one improvement to this file" < "%f" > "reviews\%~nf.md"
```

```powershell
$env:TEH_AUTO = "1"
teh "check that the docs build without warnings" | Set-Content report.txt
if ($LASTEXITCODE -eq 0) { "ok" } else { "teh ended with exit code $LASTEXITCODE" }

$env:TEH_OUTPUT = "json"
(teh "how many Python files are here?" | ConvertFrom-Json).answer     # ConvertFrom-Json: PowerShell 3.0 and later
$env:TEH_OUTPUT = $null

foreach ($f in Get-ChildItem src\*.py) {          # one run per file
    Get-Content -Encoding UTF8 $f.FullName | teh "suggest one improvement to this file" | Set-Content "reviews\$($f.BaseName).md"
}
```

Every morning, a summary of yesterday's commits:

```sh
# crontab -e
0 8 * * * cd ~/project && TEH_AUTO=1 teh "summarise yesterday's commits for the team" > ~/summary.txt
```

On Windows, put the run in a `.cmd` file, with its settings, and schedule that (from cmd or PowerShell):

```bat
@echo off
rem C:\project\summary.cmd
cd /d C:\project
set "TEH_BASE_URL=opencode-go"
set "TEH_MODEL=deepseek-v4.1-flash"
set "TEH_API_KEY=<your key>"
set "TEH_AUTO=1"
call teh "summarise yesterday's commits for the team" > "%USERPROFILE%\summary.txt"
```

```bat
schtasks /create /tn teh-summary /sc daily /st 08:00 /tr C:\project\summary.cmd
```

## Several setups

Each run uses one provider, model and key, so keep setups as short commands of their own.

sh, bash, zsh: aliases, e.g. in `~/.bashrc`:

```sh
alias teh-claude='TEH_BASE_URL=anthropic TEH_MODEL=claude-opus-5-5 TEH_API_KEY=$(cat ~/.keys/anthropic) teh'
alias teh-cheap='TEH_BASE_URL=opencode-go TEH_MODEL=deepseek-v4.1-flash TEH_API_KEY=$(cat ~/.keys/opencode) teh'
alias teh-local='TEH_BASE_URL=ollama TEH_MODEL=qwen3 TEH_CONTEXT_WINDOW=32000 teh'   # on your machine, no key
alias teh-review='TEH_ROLE="a meticulous code reviewer" teh-claude'                   # a role on top of a setup
```

Reading the key from a file (or a password manager, `$(pass show anthropic)`) keeps it out of your shell history.

cmd: a `.cmd` file per setup, in a folder on `PATH`. `setlocal` keeps its settings from leaking into your session:

```bat
@echo off
rem teh-cheap.cmd
setlocal
set "TEH_BASE_URL=opencode-go"
set "TEH_MODEL=deepseek-v4.1-flash"
set /p TEH_API_KEY=< "%USERPROFILE%\.keys\opencode"
call teh %*
```

PowerShell: functions in your profile (`notepad $PROFILE`). Each sets its settings for the run, then puts back what was there:

```powershell
function teh-with($settings, $arguments) {
    $saved = @{}
    foreach ($name in $settings.Keys) { $saved[$name] = [Environment]::GetEnvironmentVariable($name); [Environment]::SetEnvironmentVariable($name, $settings[$name]) }
    $input | teh @arguments
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
}
function teh-cheap { $input | teh-with @{ TEH_BASE_URL = "opencode-go"; TEH_MODEL = "deepseek-v4.1-flash"; TEH_API_KEY = (Get-Content "$HOME\.keys\opencode") } $args }
function teh-local { $input | teh-with @{ TEH_BASE_URL = "ollama"; TEH_MODEL = "qwen3"; TEH_CONTEXT_WINDOW = "32000" } $args }
```

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `TEH_BASE_URL` | required | A provider name (see [Providers](#providers)) or any API URL |
| `TEH_MODEL` | required | Model id; `/model` changes it in chat |
| `TEH_API_KEY` | none | API key for the provider. Not needed for local servers |
| `TEH_EFFORT` | provider default | Reasoning effort: `none`, `minimal`, `low`, `medium`, `high`, `xhigh` or `max` (which work depends on the model; anything else is refused at startup); `/effort` changes it in chat |
| `TEH_AUTO` | off | `1` runs commands without asking |
| `TEH_MAX_TOKENS` | `16000` | Max output tokens per reply |
| `TEH_CONTEXT_WINDOW` | `262144` | Context size at which `teh` compacts the conversation (see [Compaction](DESIGN.md#compaction)). Keep it a little below the model's real limit; local models often need a smaller one, e.g. `32000` |
| `TEH_THINKING` | `0` (hidden) | Show the model's reasoning, cut to this many characters |
| `TEH_FORMAT` | from the URL | `anthropic` or `openai` API format |
| `TEH_OUTPUT` | text | `json` prints one-shot results as one JSON object |
| `TEH_AGENTS_MD` | on | `0` turns off reading `AGENTS.md` files (see [AGENTS.md](DESIGN.md#agentsmd)) |
| `TEH_CACHE_RETENTION` | provider default | `long` keeps the prompt cache longer where supported: 1 hour on Anthropic, 24 hours on OpenAI. Costs more to write; worth it for chat with long pauses |
| `TEH_ROLE` | a helpful assistant | Who the model is: the system prompt opens with "You are <role>". A specific role can steer the model, e.g. `a senior Go developer reviewing for concurrency bugs` |
| `TEH_COMMAND_TIMEOUT` | `120` | Seconds before a command the model runs is stopped. `0` means no limit |
| `TEH_OUTPUT_LIMIT` | `10000` | Characters of a command's output the model sees. Longer output is cut in the middle and saved in full (see [How commands run](DESIGN.md#how-commands-run)) |
| `TEH_TOKEN_BUDGET` | `0` (no limit) | Tokens the whole run may use, counted as the status line's `Σ` (input and output, cached included). The run stops before the call that would go past it; `/budget` changes it in chat (see [Budgets](#budgets)) |
| `TEH_TURN_BUDGET` | `0` (no limit) | Model calls for one prompt. When it's reached, finished commands are kept and you can say `continue`; `/budget` changes it in chat (see [Budgets](#budgets)) |
| `TEH_SHELL` | the shell you're in | Shell to run commands in: `bash`, `zsh`, `sh`, `pwsh`, `powershell`, `cmd`, … (see [Shells](DESIGN.md#shells)) |

At startup, `teh` warns about any `TEH_` variable it doesn't know, e.g. `unknown setting TEH_MODLE: did you mean TEH_MODEL?`, and stops with a clear message if a setting has a value it can't use: a number setting that isn't a whole number, or a setting with fixed values (`TEH_AUTO`, `TEH_AGENTS_MD`, `TEH_FORMAT`, `TEH_OUTPUT`, `TEH_CACHE_RETENTION`) set to something else, e.g. `TEH_AUTO=true`. Those values may be in any case.

## One-shot results

| Exit code | `ended` (JSON) | Meaning |
|---|---|---|
| 0 | `done` | Done |
| 1 | `error` | Error: the API returned an error, or the network failed |
| 2 | `refused` | The model or provider refused |
| 3 | `context_full` | The context window was full, and compacting didn't help (or failed) |
| 4 | `cut_off` | The reply was cut off at `TEH_MAX_TOKENS` |
| 5 | `budget` | `TEH_TOKEN_BUDGET` or `TEH_TURN_BUDGET` was reached (`error` says which) |
| 130 | `cancelled` | Cancelled with Ctrl+C |

With `TEH_OUTPUT=json`, stdout gets one object instead of the answer text:

```json
{"ended": "done", "answer": "There are 12 Python files.", "error": null, "model": "claude-opus-5-5",
 "tokens": {"input": 2103, "cached": 640, "output": 95, "context": 1550},
 "commands": [{"command": "find . -name '*.py' | wc -l", "exit": 0}], "compactions": 0}
```

Each command has its exit code; a command that was stopped (it timed out, or its output passed 5,000,000 bytes) has `"exit": null`, and a declined one has `"declined"` with the message the model was given.

## Chat commands

The startup segment shows what `teh` found: OS, shell, working directory, the session's scratch folder, `AGENTS.md`, API, caching and model settings, the model's role, and any budgets.

| Command | What it does |
|---|---|
| `/model <id>` | Switch to another model of the same provider, from the next call on |
| `/effort <level\|off>` | Change the reasoning effort |
| `/budget [tokens N \| calls N \| off]` | Change the budgets: `N` is a whole number, `0` for no limit (see [Budgets](#budgets)) |
| `/compact [what to keep]` | Replace the conversation with a summary (see [Compaction](DESIGN.md#compaction)) |
| `/undo` | Remove the last prompt and everything after it from the conversation; run it again for the one before. A changed file stays changed |
| `/clear` | Start a new conversation |
| `/help` | Show all options |
| `/quit` | Exit |

Commands that change something answer with the status line as it now stands; on their own, `/model`, `/effort` and `/budget` just show it.

## Budgets

Two optional limits, both off by default (`0`):

- **`TEH_TOKEN_BUDGET`**: tokens for the whole run, a one-shot run or a chat session, counted as the status line's `Σ` shows them: input and output, cached tokens included.
- **`TEH_TURN_BUDGET`**: model calls for one prompt, the guard against a model stuck repeating itself. In a one-shot run there's one prompt, so it's the limit for the run.

The run stops before the call that would go over. A one-shot run ends with exit code 5 (`"ended": "budget"` in JSON). In chat, a line says which budget was reached; say `continue` to go on (after the token budget, raise it first with `/budget tokens N`). `/budget` changes either budget mid-chat: `/budget tokens 2000000`, `/budget calls 50`, `/budget calls 0` (no limit), or `/budget off` for both.

A CI job with a ceiling:

```sh
TEH_AUTO=1 TEH_TOKEN_BUDGET=500000 TEH_TURN_BUDGET=40 teh "fix the failing tests"
```

```bat
set "TEH_AUTO=1" & set "TEH_TOKEN_BUDGET=500000" & set "TEH_TURN_BUDGET=40"
teh "fix the failing tests"
```

```powershell
$env:TEH_AUTO = "1"; $env:TEH_TOKEN_BUDGET = "500000"; $env:TEH_TURN_BUDGET = "40"
teh "fix the failing tests"
```

## The status line

```
· claude-opus-5-5 · medium · 12.4s · in 48,210 (45,900 cached) · out 1,204 · Σ 312,877 (241,350 cached) · ctx 49,414/262,144 (19%)
```

| Field | Meaning |
|---|---|
| `12.4s` | How long the reply took, including retries |
| `in` (`cached`) | Input tokens for this call: the whole conversation, resent every call. The cached part costs about a tenth as much |
| `out` | Output tokens for this reply |
| `Σ` (`cached`, `budget`) | Session totals, how much of them came from the cache, and `TEH_TOKEN_BUDGET` when one is set |
| `ctx` | Context used, out of `TEH_CONTEXT_WINDOW`. When it passes half, `teh` suggests `/compact` once (it never compacts by itself before the window is full); it warns after every call from 80%, and compacts the conversation at 100% |
| `calls` | Model calls for this prompt out of `TEH_TURN_BUDGET`, e.g. `3/40 calls`, shown only when one is set |

While waiting, a live `· thinking… 7s` timer is shown, in a terminal only.

## Saving tokens

- **`/clear`** between unrelated tasks, **`/compact`** in long ones, and **`/undo`** after a turn that went the wrong way: every call resends the whole conversation.
- **Lower `TEH_EFFORT`** for routine work, and use **`TEH_CONTEXT_WINDOW`** as a hard cap on conversation size.
- **Keep `AGENTS.md` short:** it's sent with every call.
- **`TEH_CACHE_RETENTION=long`** for chat with long pauses, where the provider offers it.

## Safety

- **The approval prompt is the main safeguard.** With `TEH_AUTO=1` (or `a`), commands run unseen, and since the model reads web pages, a page could try to steer it. The web helper can send data (`-d`, `--json`, any `-X` method) as well as read pages, so check what a `teh-fetch` command sends, and where, before approving it.
- **Text from the web:**
  - The helper leaves out hidden elements (`hidden`, `aria-hidden`, `display:none`, `visibility:hidden`). Text hidden by a page's stylesheets can't be detected this way.
  - It labels its output as data, and the model is told never to follow instructions found in it.
- **Hidden characters:** control characters and invisible or direction-changing Unicode are removed from web text. They're also shown as a visible `�` in the model's answers, its reasoning and the commands you approve, so a command can't look different from what it is.
- **`AGENTS.md`** is read from the project root down to the working directory, never from above the project root or your home folder (see [AGENTS.md](DESIGN.md#agentsmd)). It's loaded whenever present, so use `TEH_AGENTS_MD=0` in projects you don't trust.
- **The model's commands don't see `teh`'s settings.** Every `TEH_` variable, `TEH_API_KEY` included, is removed from their environment. The one they get is `TEH_SCRATCH`, the scratch folder's path, which `teh` sets itself for the web helper. The rest of your environment is passed on unchanged, so a key you've exported under another name (e.g. `ANTHROPIC_API_KEY`) is still visible to them.

## Providers

`TEH_BASE_URL` accepts these names, or any OpenAI-compatible or Anthropic API URL:

`anthropic` `openai` `openrouter` `opencode` `opencode-go` `mistral` `deepseek` `groq` `gemini` `xai` `nanogpt` `nanogpt-sub` `venice` `together` `fireworks` `cerebras` `moonshot` `zai` `minimax` `qwen` `cohere` `huggingface` `deepinfra` `sambanova` `nebius` `novita` `chutes` `featherless` `ollama` `lmstudio`

`ollama` and `lmstudio` run on your own machine and need no key. The API format is Anthropic's when the URL contains "anthropic", otherwise OpenAI's (`TEH_FORMAT` overrides it). How providers differ, and how each one's prompt cache is used, is in [DESIGN.md](DESIGN.md#providers).

## Tests

No API key, no network: the tests run against fake API servers on your machine.

Linux and macOS (sh, bash, zsh):

```sh
tests/unix/run.sh              # every suite (about 30 seconds)
tests/unix/run.sh core fetch   # some of them
tests/unix/run.sh --changed    # only the suites affected by what changed since they last passed
cd tests && python3 -m unittest test_units   # the unit tests alone
```

Windows (cmd or PowerShell; Python only, the suites run commands in cmd and PowerShell themselves):

```bat
python tests\windows\run.py              & rem every suite (about 40 seconds)
python tests\windows\run.py core fetch   & rem some of them
python tests\windows\run.py --changed    & rem only the suites affected by what changed since they last passed
cd tests && python -m unittest test_units
```

In PowerShell, the same lines without the `& rem` comments (`#` there).

GitHub Actions runs every suite on each push and pull request, on Linux and on Windows, with Python 3.10, 3.12 and 3.14. What each suite covers, and how they're built, is in [DESIGN.md](DESIGN.md#tests) and [`tests/README.md`](tests/README.md).

## Acknowledgements

teh c kosong peng

## License

`teh` is licensed under the [Mozilla Public License 2.0](LICENSE). You can use it in any project, open or closed; if you distribute a changed `teh.py`, its source (the changed file) stays under the MPL. The notice at the top of `teh.py` travels with the file when it's copied on its own.
