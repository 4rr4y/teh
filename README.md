# teh

**t**oken **e**fficient **h**arness: a minimal LLM agent in one Python file, with no dependencies. The name is also a nod to Singapore's *teh*.

You give it a task; the model gets one tool, your shell, and runs commands until the task is done, asking you before each one. It works with Anthropic's API and any OpenAI-compatible API (about 30 providers built in), on Linux, macOS and Windows, and shows exactly how many tokens each reply costs.

`teh.py` has three roles: **the harness** (`teh.py ["task"]`), **a web helper** (`teh.py --fetch URL [word ...]`) that reads web pages as plain text, and **an edit helper** (`teh.py --edit FILE`) that applies exact search-and-replace edits. The model uses both helpers through the shell, as `teh-fetch` and `teh-edit`, so it still has a single tool.

## How it saves tokens

Every call resends the whole conversation, so most of these decisions keep the conversation small or let the provider read it from its cache.

**The prompt and the tool**
- The model gets a single tool, the shell, so the tool definition sent with every call is about 50 tokens.
- Web pages and search go through the same shell tool, as `teh-fetch`, instead of a second tool, and the short name saves tokens in every call that uses it.
- The system prompt is about 400 tokens and never changes during a session, so the provider can serve it from its cache on every call.
- The system prompt names the scratch folder by its environment variable rather than its random path, so it is identical in every session started in the same folder and a new session can reuse the cache.
- The system prompt lists the search sources and says general search engines don't work, so the model doesn't spend a call discovering either.
- `AGENTS.md` files are limited to 32,768 characters in all, with a note telling the model where to read the rest, because they are sent with every call.

**Caching**
- `teh` switches on prompt caching where a provider makes it opt-in, sends a session id where a provider uses one to find the cache, and reads cache hits wherever a provider reports them.
- `TEH_CACHE_RETENTION=long` keeps the cache for an hour (Anthropic) or a day (OpenAI), for chat with long pauses.

**What the model is told**
- The model is told to be concise, with no preamble or narration around tool calls, because output tokens cost about five times as much as input.
- The model is told to read only what it needs (`rg -n`, `sed -n`, `head`, or its shell's own: `Select-String` in PowerShell, `findstr` in cmd) rather than whole files.
- For totals, counts and comparisons over many rows of data (CSV, logs, tables), the model is told to write a script that prints the result rather than work it out by reading, and in its replies not to repeat file contents or command output (output costs about 5× input). The benchmark showed what not to say: telling it to read in parts or filter output made it skim and miss details, so it isn't.
- The model is told to run independent slow commands (test suites, builds, downloads) in parallel in one call, each writing its output to a file of its own in the scratch folder, then to wait for all of them: `A > $TEH_SCRATCH/a.log 2>&1 & B > $TEH_SCRATCH/b.log 2>&1 & wait` in Unix shells, `Start-Job` and `Wait-Job` in PowerShell. Separate files keep their outputs from mixing. cmd can't wait for background jobs, so there it isn't told.
- Files are edited with `teh-edit`, which replaces exact text, so a one-line fix costs a few lines of output instead of a whole file, and the model is told never to rewrite a whole file to change part of it.
- All of a file's edits go in one `teh-edit` call, because every extra call resends the whole conversation.
- An edit whose text differs from the file only in indentation is applied anyway, when there's one clear place for it, instead of costing a call to send it again.
- A failed edit is explained with the file's closest lines, numbered (and whether only the indentation differs), so the model can fix it without a call to read the file again.
- Edits that apply are kept when another in the same call fails, so the model sends again only the one that failed.
- The model is told to combine related commands into one call, because every extra call resends the whole conversation.

**Command output**
- Terminal colour codes and the intermediate states of progress bars are removed, because they carry no information.
- A run of identical lines is shown once with a count, but only when the count is shorter than the lines it replaces.
- A line over 500 characters (minified code, base64) keeps only its first and last 200, so a few such lines can't crowd out the rest of the output.
- Output over 10,000 characters is cut in the middle and saved in full, so the model can `grep` the saved copy instead of rerunning the command.
- A command run again shows only the lines that changed since its last run, but only when that is under half as long as the output itself.
- A command is stopped once its output passes 5,000,000 bytes, so a runaway command can't produce more than the model would ever be shown.

**Piped input**
- Piped input is cleaned like command output, and cut only if it would take more than half the context window.

**The web helper**
- Pages are turned into text, with scripts, styles, menus, footers and hidden elements removed.
- Links are numbered in the text and listed once at the end, so a long address isn't repeated where it appears.
- Given words to look for, the helper prints only the lines containing them, and otherwise only the start of the page, with the full text saved for `grep`.
- Sites with a cleaner version of a page (GitHub, PyPI, npm, crates.io, Stack Exchange, Wikipedia, Apple's docs) are read from that version instead.
- JSON is printed one item per line so the word search can find things in it, and HTML inside it is turned into text.
- Search results are three lines each (title, link, details), eight per search, with the API's full response saved.
- An API's own explanation of an error is shown, so the model can fix its request in one attempt instead of guessing.

**Long conversations**
- When the context window fills, the conversation is replaced with a summary, even in the middle of a task, which then continues.
- The summary request is added to the end of the unchanged conversation, so the provider reads the whole history from its cache.
- The summary is at most about 400 words under fixed headings, and leaves out anything that can be read from disk again.
- Your requests are copied into the new conversation by `teh` itself, so the model doesn't spend output tokens repeating them.
- The full transcript is saved for `grep`, so the summary can stay short without losing details.
- The context is counted before each call, including an estimate of what was added since the last one, so compaction happens before the call that would overflow rather than after.

**Your controls**
- The status line after each reply shows the tokens it cost, the session total and how much came from the cache.
- `/compact` summarises a long conversation, `/undo` drops a turn that went the wrong way, `/clear` starts a new one, and `/effort` lowers the reasoning effort for routine work.
- `TEH_TOKEN_BUDGET` caps the tokens a whole run may use, and `TEH_TURN_BUDGET` caps the model calls for one prompt, so a runaway task can't run up a bill; `/budget` changes them mid-chat.

## Install and set up

```sh
chmod +x teh.py && ln -s "$PWD/teh.py" ~/.local/bin/teh    # or run: python3 teh.py

export TEH_BASE_URL=anthropic TEH_MODEL=claude-opus-5-5 TEH_API_KEY=sk-ant-...
teh
```

`TEH_BASE_URL` is a [provider name](#providers) or any API URL. All settings are environment variables; see [Settings](#settings).

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

When a command is shown for approval: `y` runs it, `a` runs it and every later one, Enter declines, and **any other text declines and tells the model what to do instead**, e.g. `use rg instead of grep -r`. Ctrl+C stops the model mid-turn; commands that already finished stay in the conversation, so you can say `continue`.

## Scripts and pipelines

With a task (or piped input), `teh` runs once and exits. The answer, the model's last reply, goes to stdout at the end; its earlier replies, status lines and commands go to stderr, so pipes get only the answer.

Piped input is added to the task, cleaned like command output (terminal colour codes removed, any bytes accepted). It's meant to be read whole, so it's cut only if it would take more than half of `TEH_CONTEXT_WINDOW` (about 4 characters a token): the model then gets the start and the end, and the whole of it is saved in the scratch folder for `grep`. At most 5,000,000 characters are read.

```sh
teh "what's using the most disk space here?"                    # one question, one answer
git diff | teh "review this change"                             # piped input, plus a task
git diff --staged | teh "write a commit message" > msg.txt      # the answer, into a file
cat error.log | teh "explain this error" | less
teh "list the TODOs in this repo as a Markdown checklist" | tee TODO.md
teh "summarise this file in 3 lines" < notes.txt                # a file as input
TEH_AUTO=1 teh "run the tests and fix any failures"             # no approval prompts
```

**No terminal** (CI, cron, a script run in the background): set `TEH_AUTO=1`. There's nobody to approve commands, so without it the run stops with `no terminal to approve commands: set TEH_AUTO=1` (exit code 1).

The **exit code** says how the run ended, and `TEH_OUTPUT=json` prints the whole result as one JSON object:

```sh
if TEH_AUTO=1 teh "check that the docs build without warnings" > report.txt; then
    echo "ok"
else
    echo "teh ended with exit code $?"            # 1 error, 2 refused, 3 context full, 4 cut off, 5 budget, 130 cancelled
fi

TEH_OUTPUT=json TEH_AUTO=1 teh "how many Python files are here?" | jq -r .answer
TEH_OUTPUT=json TEH_AUTO=1 teh "update the changelog" | jq '.tokens, .commands'

for f in src/*.py; do                             # one run per file
    teh "suggest one improvement to this file" < "$f" > "reviews/$(basename "$f").md"
done
```

```
# crontab: a morning summary of yesterday's commits
0 8 * * * cd ~/project && TEH_AUTO=1 teh "summarise yesterday's commits for the team" > ~/summary.txt
```

## Several setups

Each run uses one provider, model and key, so keep setups as aliases, e.g. in `~/.bashrc`:

```sh
alias teh-claude='TEH_BASE_URL=anthropic TEH_MODEL=claude-opus-5-5 TEH_API_KEY=$(cat ~/.keys/anthropic) teh'
alias teh-cheap='TEH_BASE_URL=opencode-go TEH_MODEL=deepseek-v4.1-flash TEH_API_KEY=$(cat ~/.keys/opencode) teh'
alias teh-local='TEH_BASE_URL=ollama TEH_MODEL=qwen3 TEH_CONTEXT_WINDOW=32000 teh'   # on your machine, no key
alias teh-review='TEH_ROLE="a meticulous code reviewer" teh-claude'                   # a role on top of a setup
```

Reading the key from a file (or a password manager, `$(pass show anthropic)`) keeps it out of your shell history.

On Windows, set variables the way your shell does: `$env:TEH_MODEL = "claude-opus-5-5"` in PowerShell, `set TEH_MODEL=claude-opus-5-5` in cmd, then run `py teh.py`.

## The web helper on its own

```sh
teh --fetch https://pypi.org/project/requests/ version                 # lines containing "version"
teh --fetch https://docs.python.org/3/library/json.html dumps loads    # lines containing either word
teh --fetch https://github.com/python/cpython                          # the start of the README
teh --fetch -H "Authorization: Bearer $TOKEN" https://api.github.com/user/repos name   # a header
teh --fetch --json '{"q": "teh"}' https://api.example.com/search                     # a JSON POST
teh --fetch -X DELETE https://api.example.com/items/7                                # any method
```

---

# Reference

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `TEH_BASE_URL` | required | A provider name (see [Providers](#providers)) or any API URL |
| `TEH_MODEL` | required | Model id; `/model` changes it in chat |
| `TEH_API_KEY` | none | API key for the provider. Not needed for local servers |
| `TEH_EFFORT` | provider default | Reasoning effort: `none`, `minimal`, `low`, `medium`, `high`, `xhigh` or `max` (which work depends on the model; anything else is refused at startup); `/effort` changes it in chat |
| `TEH_AUTO` | off | `1` runs commands without asking |
| `TEH_MAX_TOKENS` | `16000` | Max output tokens per reply |
| `TEH_CONTEXT_WINDOW` | `262144` | Context size at which `teh` compacts the conversation (see [Compaction](#compaction)). Keep it a little below the model's real limit |
| `TEH_THINKING` | `0` (hidden) | Show the model's reasoning, cut to this many characters |
| `TEH_FORMAT` | from the URL | `anthropic` or `openai` API format |
| `TEH_OUTPUT` | text | `json` prints one-shot results as one JSON object |
| `TEH_AGENTS_MD` | on | `0` turns off reading `AGENTS.md` files (see [AGENTS.md](#agentsmd)) |
| `TEH_CACHE_RETENTION` | provider default | `long` keeps the prompt cache longer where supported: 1 hour on Anthropic, 24 hours on OpenAI. Costs more to write; worth it for chat with long pauses |
| `TEH_ROLE` | a helpful assistant | Who the model is: the system prompt opens with "You are <role>". A specific role can steer the model, e.g. `a senior Go developer reviewing for concurrency bugs` |
| `TEH_COMMAND_TIMEOUT` | `120` | Seconds before a command the model runs is stopped. `0` means no limit |
| `TEH_OUTPUT_LIMIT` | `10000` | Characters of a command's output the model sees. Longer output is cut in the middle and saved in full (see [How commands run](#how-commands-run)) |
| `TEH_TOKEN_BUDGET` | `0` (no limit) | Tokens the whole run may use, counted as the status line's `Σ` (input and output, cached included). The run stops before the call that would go past it; `/budget` changes it in chat (see [Budgets](#budgets)) |
| `TEH_TURN_BUDGET` | `0` (no limit) | Model calls for one prompt. When it's reached, finished commands are kept and you can say `continue`; `/budget` changes it in chat (see [Budgets](#budgets)) |
| `TEH_SHELL` | the shell you're in | Shell to run commands in: `bash`, `zsh`, `sh`, `pwsh`, `powershell`, `cmd`, … |

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

## Chat

The startup segment shows what `teh` found: OS, shell, working directory, the session's scratch folder, `AGENTS.md`, API, caching and model settings, the model's role, and any budgets. It's printed only in chat mode.

| Command | What it does |
|---|---|
| `/model <id>` | Switch to another model of the same provider, from the next call on |
| `/effort <level\|off>` | Change the reasoning effort |
| `/budget [tokens N \| calls N \| off]` | Change the budgets: `N` is a whole number, `0` for no limit (see [Budgets](#budgets)) |
| `/compact [what to keep]` | Replace the conversation with a summary (see [Compaction](#compaction)) |
| `/undo` | Remove the last prompt and everything after it from the conversation (see below) |
| `/clear` | Start a new conversation |
| `/help` | Show all options |
| `/quit` | Exit |

**`/undo`** is for a turn that went the wrong way: it removes your last prompt and everything the model did after it, so none of it is resent with later calls. Run it again to remove the prompt before. It removes only the end of the conversation, so everything before it is still read from the prompt cache, as after any finished turn: it never costs more than leaving the turn in. It doesn't undo what the turn's commands did (a changed file stays changed); it says how many commands ran. Prompts before a compaction (or `/clear`) can't be undone, since they're part of the summary.

Commands that change something (`/model`, `/effort`, `/budget`, `/undo`, `/clear`) answer with the status line as it now stands, rather than a confirmation: the effort, the totals and token budget, the context and the call budget all show there. `/model`, `/effort` or `/budget` on its own changes nothing, so it's also a way to see the status line between prompts.

**`/model`** checks the name against the models the provider lists (`GET /models`) and refuses one it doesn't list, suggesting the closest names; if the provider doesn't list its models, the switch goes ahead and an unknown name fails at the next call, with the provider's own error. `/effort` likewise refuses a level that no provider accepts (a typo). Models don't share a prompt cache, so after a switch the next call reads the whole conversation at full price: `teh` says so when there is a conversation to re-read. The API format (`TEH_FORMAT`) can't change mid-chat.

Ctrl+D exits (on Windows: Ctrl+Z, then Enter), as does Ctrl+C at an empty prompt. Pasted lines arrive as one prompt: terminals that mark pastes are handled by readline, and for others `teh` joins lines that arrive at the same moment.

## How commands run

- **In a new shell each time,** started in the directory where you launched `teh`, so `cd` and environment variables don't carry over. The shell gets your environment without `teh`'s own `TEH_` settings (see [Safety](#safety)).
- **With no input:** a command that asks a question gets no answer and finishes at once, instead of hanging. The model is told to use options like `-y` and `git commit -m`.
- **Background jobs keep running:** `npm run dev &` returns at once and the server stays up.
- **Stopped after `TEH_COMMAND_TIMEOUT` seconds** (120 by default; `0` for no limit), with everything they started. The model still gets the output so far. Ctrl+C stops the running command too.
- **Stopped when the output passes 5,000,000 bytes,** so a runaway command (`yes`, a logging loop) can't fill the disk before the timeout. The model is told to write large output to a file and read only what it needs. Only output `teh` captures counts: a command writing to a file isn't limited. It's a constant in `teh.py`, `OUTPUT_MAX_BYTES`, rather than a setting.
- **Output:** normal and error output together, in order. What carries no information is removed first: terminal colour codes, the intermediate states of progress bars, and runs of identical lines (kept once, with a count, when the count is shorter). A line over 500 characters (minified code, a lockfile, base64) keeps its first and last 200, e.g. `[… 2,800 characters]` in between, so a few such lines can't push the rest of the output out; the full output is then saved, and the model told where. Output longer than `TEH_OUTPUT_LIMIT` (10,000 characters by default) is cut in the middle, at line breaks: the model sees the first and last lines, and a note saying how much was left out and where the **full output is saved** in the scratch folder, e.g. `[… 98,000 characters (17,000 lines) omitted; full output in /tmp/teh-…/output-1.txt: use grep or sed -n to read it]`. So the model can read any part of it with `grep` or `sed -n` instead of running the command again, which matters for slow, costly or one-off commands. Each result is resent on every later call, so keeping it short keeps the cost down.
- **Run again:** when the model runs a command it ran earlier in the conversation (the tests after a fix, `git status`, a build), it gets only what changed: `[the same output as the last time this command ran]`, or the changed lines as a diff, with a line around each change. The two are compared as they would be sent, and the changes are used only when under half as long as the output (a diff is harder to read). Otherwise the model gets the output as usual, and also when the earlier result is no longer in the conversation (after compaction or `/clear`), or when the output is over 100,000 characters.
- **Scratch folder:** each session gets a fresh folder in the system temp folder for temporary scripts, downloads and notes, and the model is told to use it rather than your project. The system prompt names it by its environment variable, `TEH_SCRATCH`, not its path, which is random (see [Prompt caching](#prompt-caching)). `teh` deletes it on exit, including when the terminal is closed or `teh` is stopped with `kill`. It's only left behind if `teh` is killed outright (`kill -9`, a crash), and probably when a Windows console window is closed.
- **Refusals:** if the model or provider refuses, `teh` says so with the reason, and drops the refused prompt so you can carry on.

## Budgets

Two optional limits, both off by default (`0`):

- **`TEH_TOKEN_BUDGET`**: tokens for the whole run, a one-shot run or a chat session, counted as the status line's `Σ` shows them: input and output, cached tokens included. It's a token budget, not a cost budget: cached tokens cost about a tenth as much, but count in full, so a long chat reaches it sooner than its cost would suggest.
- **`TEH_TURN_BUDGET`**: model calls for one prompt, the guard against a model stuck repeating itself. In a one-shot run there's one prompt, so it's the limit for the run.

Both are checked before each model call, including a compaction call: the token budget adds what has been used to what the next call would resend (the conversation so far, and what was added since), so the run stops before the call that would go over, not after it. When a budget is reached:

- **One-shot:** the run ends with exit code 5, and `"ended": "budget"` with `TEH_OUTPUT=json`, whose `error` says which budget and how far it got. Commands that finished are listed as usual.
- **Chat:** a line says which budget was reached, and how to go on. Finished commands are kept, so `continue` picks up where the model stopped (rather than repeating the prompt, which would redo the work). After the turn budget, `continue` gets another allowance of calls; after the token budget, which covers the whole session, raise it first with `/budget tokens N`.

`/budget` changes either budget mid-chat, starting from the settings: `/budget tokens 2000000`, `/budget calls 50`, `/budget calls 0` (no limit), or `/budget off` for both.

```sh
TEH_AUTO=1 TEH_TOKEN_BUDGET=500000 TEH_TURN_BUDGET=40 teh "fix the failing tests"   # a CI job with a ceiling
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

## Editing files

The model edits files with `teh-edit FILE`, giving it one or more blocks on stdin, each replacing exact text:

```sh
teh-edit app.py <<'EOF'
<<<<<<< SEARCH
def total(items):
    return sum(items)
=======
def total(items):
    return sum(i.price for i in items)
>>>>>>> REPLACE
EOF
```

Editing through the shell (`sed -i`, heredocs) is where models go wrong most: escaping breaks on slashes, quotes and newlines, and after a failed edit they often rewrite the whole file, the costliest output there is. So `teh-edit` takes the format models know best, the one Aider uses (it looks like a Git conflict):

- **Exact:** a block applies only if its SEARCH text appears in the file exactly once, so an edit never lands in the wrong place.
- **Indentation forgiven, when it's clear-cut:** a SEARCH that isn't found exactly, but whose lines are found once when whitespace at either end is ignored, and that is indented by the same amount more (or less) than the file on every line, is applied there, with REPLACE indented by that amount too. The output says so (`at line 9 SEARCH matched only ignoring whitespace, so REPLACE was indented to fit`), so the model learns the file's real indentation. Anything less certain (tabs for spaces, uneven differences, more than one place) gets the usual explanation instead. Re-sending a block costs a whole call, and a mis-indented SEARCH is the most common reason for one.
- **All of a file's edits in one call:** the model is told to send them together, as every extra call resends the conversation. Blocks apply in order.
- **Failures explained, cheaply:** a SEARCH that isn't found gets the file's closest lines, numbered, and a note if only the indentation differs; one found more than once gets the line numbers of each. The model can fix the block without reading the file again.
- **Only failed blocks need sending again:** the blocks that apply are written even when another fails, and the output lists only the ones that didn't (exit code 1).
- **Short success output:** one line, e.g. `edited app.py: 3 of 3 blocks applied (at lines 12, 40, 88)`; the model wrote the change, so it isn't echoed back.
- **Files as they were:** Windows line endings (CRLF) are kept, and the blocks are matched against them.
- **New files:** a single block with an empty SEARCH creates the file, and its folders.

In PowerShell, pipe the blocks in with a here-string (`@'…'@ | teh-edit FILE`); in cmd, from a file (`teh-edit FILE < blocks.txt`). The system prompt describes the format in one sentence, about 25 tokens.

## Reading web pages

The model reads the web only through the helper; the system prompt rules out `curl`, `wget` and similar. The model runs it as `teh-fetch`: a tiny launcher for `teh.py --fetch` in the scratch folder, which is put first on the search path for its commands. A short name saves tokens in every call that uses it, and in the conversation afterwards. On Windows the launcher is a `.cmd` file. In PowerShell, which would drop the quotes around an address with `&` in it when running a `.cmd` file, `teh` instead adds a `teh-fetch` function to each command, so such addresses arrive intact. The helper writes UTF-8 whenever its output isn't a terminal, so non-English pages come through correctly on Windows too. (These Windows paths haven't been tested on Windows itself.)

- **Text, not HTML:** scripts, styles, menus and page chrome are removed; headings, lists and code blocks are kept. Links become `[3]`, listed once at the end.
- **Only what's asked for:** with words, the lines containing any of them, numbered, with context; without, the start of the page. The full text is saved in the scratch folder (or a `teh-fetch` temp folder when run on its own), for `grep` or `sed`.
- **Cleaner sources first** (the `WEB_REWRITES` table, one line per site):
  - GitHub: raw files and READMEs
  - PyPI, npm and crates.io: their JSON APIs
  - Stack Overflow: the Stack Exchange API
  - Wikipedia: the source text
  - Apple's developer docs: their JSON version
  
  JSON is reformatted one item per line, and HTML inside it is turned into text.
- **Pages built by JavaScript:** the page's title and description are always kept, which is often all a non-browser fetch can get (YouTube, X, Instagram). Nearly empty pages get a hint to try `.md`, `/llms.txt` or an API.
- **Blocked sites:** a clear message suggesting the site's API, its RSS feed or another source. The helper doesn't disguise itself as a browser.
- **Misbehaving servers:** a dropped connection shows what arrived and says the page is incomplete; a corrupt answer gets a one-line `fetch failed`; compressed pages are unpacked only up to 5,000,000 bytes, so a small download can't expand to gigabytes; and a character set Python doesn't know is read as UTF-8. Never a traceback, which would only cost the model tokens.
- **APIs:** options for headers, other methods and request bodies, named as in curl because models already know those names. The system prompt only lists them. Requests are sent with Python's `urllib`; curl isn't used or needed.

  | Option | What it does |
  |---|---|
  | `-H 'Name: value'` | Adds a header, or replaces a default one such as `user-agent`. Repeatable |
  | `-X METHOD` | The method. Default: GET, or POST when there's data |
  | `-d DATA` | A form body. `@file` reads it from a file and `@-` from stdin, so JSON needn't be quoted for the shell. Repeatable, joined with `&` |
  | `--json DATA` | A JSON body, with `content-type` and `accept` set to JSON. `@file` and `@-` work too |

  Options can go anywhere on the line. Every other argument is the URL (the first one) or a word to look for, so commands without options work as before. A request with options goes to the URL as given, with no cleaner source from `WEB_REWRITES`. When it fails, the server's own explanation is shown if it's JSON or plain text (up to 1,000 characters), so the model can fix its request. To add an option, add its names to `WEB_OPTIONS` and handle it in `request_options()`.

**Results:**
- **Content:** on 22 sites chosen to include JavaScript-heavy ones, the key content came through on 18. The failures were Reddit (needs a login), and the New York Times, OpenAI and Medium (they block automated requests).
- **Tokens:** on 8 pages, the model received about a third of the characters `curl` gave it, and the information was there on all 8 pages, against 5 with `curl`.

## Searching

General web search engines don't work for a program that's honest about what it is. Tested from Python's standard library with the helper's own user agent: DuckDuckGo and Mojeek answer with a bot challenge, Brave with HTTP 429, and Google with a page that needs JavaScript. Bing answers, but with results unrelated to the query (for "python 3.14 release notes", pages about colonization for children), which is worse than no answer. So the helper searches sources that offer a free, official search API instead, with no key:

```sh
teh --fetch --search wikipedia fusion energy
teh --fetch --search stackexchange:cooking sourdough starter     # SOURCE:OPTION, here a Stack Exchange site
teh --fetch --search github:issues tokio select cancel
teh --fetch --search                                              # every source, what it covers, and its limit
```

Each result is three lines: title, link and details (e.g. votes and answers, stars, authors and date), so 8 results cost a few hundred tokens. The API's full response is saved for `grep`, and the model reads a result with `teh-fetch URL`. The model is told the source names in the system prompt, and that general search engines don't work, so it doesn't spend calls on them.

| Source | Covers | Limit without a key |
|---|---|---|
| `wikipedia`, `wiktionary`, `wikivoyage` | Encyclopedia, words, travel (option: language, e.g. `:de`) | Low for clients without contact details (Wikimedia's rules from 2026) |
| `wikidata` | Facts about people, places, things | As Wikipedia |
| `stackexchange` | Questions and answers (option: site, e.g. `:cooking`, `:math`; default Stack Overflow) | 300 searches a day, for all sites |
| `hackernews` | Tech news and discussion | 10,000 an hour (as reported) |
| `github` | Repositories (option: `:issues`) | 10 searches a minute |
| `npm`, `crates` | JavaScript and Rust packages | crates.io: 1 request a second |
| `mdn` | Web platform docs | None published |
| `huggingface` | Machine learning models | 500 requests per 5 minutes |
| `arxiv` | Research preprints | 1 request every 3 seconds |
| `crossref` | Published papers, all fields | 1 request a second, one at a time |
| `openfda` | US drug labels, by brand or generic name | 240 a minute, 1,000 a day |
| `openlibrary` | Books and authors | 1 request a second |
| `itunes` | Music, podcasts, films, apps (option: `:podcast`, `:music`, …) | About 20 a minute |
| `tvmaze` | TV shows | 20 requests every 10 seconds |
| `musicbrainz` | Music (option: `:release`, `:recording`) | 1 request a second |
| `archive` | The Internet Archive: books, films, audio, software | None published |
| `nasa` | NASA images and video | None published |
| `places` | Places and addresses, from OpenStreetMap | 1 request a second, no heavy use |
| `federalregister` | US federal rules and notices | None published |

**Limits:** the helper keeps requests to each source far enough apart for its limit, even across separate runs (a timestamp file in the scratch folder). If a source still refuses (HTTP 403, 429, or 503, which is how MusicBrainz says "too fast"), the message gives its limit and suggests waiting or another source.

**Identifying yourself for higher limits:** some sources give clients with contact details in their user agent more room: Wikimedia 200 requests a minute instead of 10, Open Library 3 a second instead of 1; MusicBrainz and OpenStreetMap ask for it, and Crossref serves such clients from its "polite pool". `WEB_CONTACT`, at the top of the web helper in `teh.py`, is an email or a URL that those sites (only) get in the user agent `teh-fetch/0.1 (<contact>) teh/3.x` (the `3.x` is the Python version); every other site keeps the anonymous user agent. It's set to `teh@teh.com` by default: replace it with your own email or URL, or set it to `""` to send nothing.

**Left out after testing:** Semantic Scholar, GDELT and Google Books (HTTP 429 on the first request), OpenAlex (its free budget is shared by everyone on your network and ran out at once), Europe PMC (14–31 seconds a search), Gutendex (25 seconds), Reddit and the Art Institute of Chicago (blocked), Open Food Facts (unavailable), TheMealDB (its free key is for development only).

**Adding a source:** one `SearchSource` entry in `WEB_SEARCH`: the API's URL (`{q}` the query, `{p}` the option), where the results are in its response, and short templates for each result's title, link and details (`{field}`, `{field[subfield]}`; a missing field is left out).

## Safety

- **The approval prompt is the main safeguard.** With `TEH_AUTO=1` (or `a`), commands run unseen, and since the model reads web pages, a page could try to steer it. The web helper can send data (`-d`, `--json`, any `-X` method) as well as read pages, so check what a `teh-fetch` command sends, and where, before approving it.
- **Text from the web:**
  - The helper leaves out hidden elements (`hidden`, `aria-hidden`, `display:none`, `visibility:hidden`). Text hidden by a page's stylesheets can't be detected this way.
  - It labels its output as data, and the model is told never to follow instructions found in it.
- **Hidden characters:** control characters and invisible or direction-changing Unicode are removed from web text. They're also shown as a visible `�` in the model's answers, its reasoning and the commands you approve, so a command can't look different from what it is.
- **`AGENTS.md`** is read from the project root down to the working directory, never from above the project root or your home folder (see [AGENTS.md](#agentsmd)). It's loaded whenever present, so use `TEH_AGENTS_MD=0` in projects you don't trust.
- **The model's commands don't see `teh`'s settings.** Every `TEH_` variable, `TEH_API_KEY` included, is removed from their environment. The one they get is `TEH_SCRATCH`, the scratch folder's path, which `teh` sets itself for the web helper. The rest of your environment is passed on unchanged, so a key you've exported under another name (e.g. `ANTHROPIC_API_KEY`) is still visible to them.

## Providers

`TEH_BASE_URL` accepts these names, or any OpenAI-compatible or Anthropic API URL:

`anthropic` `openai` `openrouter` `opencode` `opencode-go` `mistral` `deepseek` `groq` `gemini` `xai` `nanogpt` `nanogpt-sub` `venice` `together` `fireworks` `cerebras` `moonshot` `zai` `minimax` `qwen` `cohere` `huggingface` `deepinfra` `sambanova` `nebius` `novita` `chutes` `featherless` `ollama` `lmstudio`

`ollama` and `lmstudio` run on your own machine and need no key. The API format is Anthropic's when the URL contains "anthropic", otherwise OpenAI's (`TEH_FORMAT` overrides it).

How providers differ is kept in one table in `teh.py`, `PROVIDER_QUIRKS`. Each entry is keyed by a fragment of the API URL and lists only what differs from the plain format. Every possible key is documented in `QUIRK_DEFAULTS`:

| Key | What it says |
|---|---|
| `key_header` | Which header carries the API key (`authorization` sends `Bearer <key>`) |
| `max_tokens_field` | The max-tokens field name, e.g. `max_completion_tokens` for OpenAI |
| `effort_path` | Where the effort level goes, e.g. `reasoning.effort` for OpenRouter |
| `headers` | Extra headers for every request |
| `session_id` | Where the prompt-cache session id goes, e.g. `("body", "prompt_cache_key")` |
| `cache_marker` | Opt-in caching: send `cache_control` for models whose name contains this (`""` for all) |
| `long_cache` | Extra fields for `TEH_CACHE_RETENTION=long` |
| `cached_header` | A response header that reports cache hits |

## Prompt caching

Every call resends the whole conversation, so caching matters most for cost: a cache hit costs a fraction of the normal input price (0.1× on Anthropic and Mistral, 0.5× on Groq and Fireworks, for example). For each provider, `teh`:

- **Turns caching on** where it's opt-in: Anthropic, and Claude models through OpenRouter or NanoGPT.
- **Sends a session id** where the provider uses one to route requests to the server holding the cache: OpenAI, Mistral, Together, Cerebras, Venice and DeepInfra as `prompt_cache_key`, and xAI, Fireworks and opencode as a header. `/clear` starts a new id.
- **Reads cache hits** wherever the provider reports them (DeepSeek, Fireworks and Kimi report them in their own places).
- **Keeps the cache longer** with `TEH_CACHE_RETENTION=long`, where offered.

Other providers mostly cache automatically. The startup segment's `cache` line shows what `teh` does for the current one.

The system prompt is the same in every session started in the same folder: it names the scratch folder by its variable rather than its random path. So a new session (the next run of a script or a loop, a cron job, a restarted chat) can read the prompt from the cache left by the last one, while it's still there. That pays once the system prompt is above the provider's minimum cacheable size, e.g. with an `AGENTS.md`.

Caching only starts once a request reaches the provider's minimum size, often 1,024 tokens. On Anthropic, the cache expires after 5 minutes without a call, and changing `/effort` mid-conversation resets it once.

## AGENTS.md

[`AGENTS.md`](https://agents.md) files (instructions for coding agents: build commands, code style, …) are added to the system prompt, as in Codex and Gemini CLI:
- **From the project root down to the working directory:** every `AGENTS.md` on the way, the root's first, so the closest, most specific one reads last. Start `teh` in `packages/api` and both the repository's `AGENTS.md` and `packages/api/AGENTS.md` apply.
- **The project root** is the nearest folder, going up, that holds a Git, Mercurial or Jujutsu repository: `.git` (a folder with `HEAD` in it, or a `.git` file, as in worktrees and submodules), `.hg` or `.jj`. A stray or empty marker folder doesn't count; some machines have an empty `/tmp/.git`, which would otherwise make everything under `/tmp` one project.
- **Nothing above the project root is read,** so a file higher up can't add instructions without you knowing. Outside any repository, only the working directory's `AGENTS.md` is read.
- **Never above your home folder,** and the home folder itself counts as a project root only when you start `teh` there: if you keep your dotfiles in Git, `~/AGENTS.md` doesn't apply to every project.
- **Visible:** the startup segment's `agents` line, or a `· using …` line in one-shot mode, lists each file and its size.
- **Cost:** they're sent with every call, so keep them short.
- **Size limit:** 32,768 characters in all, the same limit as Codex's default (`AGENTS_MD_MAX` in `teh.py`). The closest file gets the room first; a file that doesn't fit is cut at a line break, and any nearer the root are left out, each with a note telling the model where to read it. (Codex fills its limit from the root instead, so it's the closest file that gets left out.) Chat mode highlights this at startup; one-shot runs say it in their `· using …` line on stderr.

## Shells

Commands run in one shell, chosen at startup:
- **Linux and macOS:** `$SHELL`, or `/bin/sh` if that isn't set.
- **Windows:**
  - PowerShell if you started `teh` from PowerShell (`pwsh` when installed), otherwise cmd. Telling the two apart is a best guess.
  - Git Bash and MSYS2 set `$SHELL`, so they use bash.
- **Anywhere:** `TEH_SHELL` overrides the choice.

The model is told the OS and shell so it uses the right syntax. PowerShell commands are passed in encoded form, so quotes reach it unchanged.

## Compaction

Every call resends the whole conversation, so long sessions get expensive. Compaction replaces the conversation with a short summary and carries on from there. It happens:
- **on request:** `/compact` in chat, optionally with what to keep, e.g. `/compact keep the database migration details`
- **automatically** when the context reaches `TEH_CONTEXT_WINDOW`, even in the middle of a task, which then continues from the summary

**How it works:**
- **The summary request is added to the end of the conversation,** with nothing else changed, so the provider reads the whole history from its prompt cache. On Anthropic, a 120,000-token conversation costs about as much as 6,000–12,000 fresh tokens to summarise.
- **The model writes short notes** under fixed headings (state, files, facts, decisions, next step), at most about 400 words. It's told to leave out anything that can be read from disk again, such as code.
- **Your requests are kept word for word.** `teh` copies them itself, so the model doesn't spend output tokens repeating them.
- **The full transcript is saved** in the scratch folder (`transcript-1.txt`, `-2.txt`, …), and the summary says where. The model can `grep` it for any detail the summary left out.
- **The new conversation** is one message with your requests, the summary and the transcript's path. It starts fresh, so it works the same with every provider, including Claude models, which reject edits to earlier history.

**What you see:**
- **Success:** a status line like `· compacted: 121,340 → about 1,500 tokens; transcript saved to …`.
- **Failure:** if compacting fails (an error, a refusal), the conversation is left unchanged. Ctrl+C leaves it unchanged too, and cancels the turn (exit code 130).
- **One attempt in a row:** if the window is full again straight after compacting, `teh` stops (exit code 3) rather than compacting again.

**When the window counts as full:** before each call, `teh` adds two things together: the conversation's size as the provider reported it after the last call, and an estimate (about 4 characters a token) of what's been added since, such as command output and your new prompt. So a large command output triggers compaction *before* the call that would go over, not after.

**Set `TEH_CONTEXT_WINDOW` a little below your model's real limit.** Compacting sends the whole conversation plus the summary request, so it needs some room. The default, 262,144, is below the limit of most hosted models. Local models often run with much smaller windows, so set it to match, e.g. `TEH_CONTEXT_WINDOW=32000`.

## Saving tokens

- **`/clear`** between unrelated tasks, **`/compact`** in long ones, and **`/undo`** after a turn that went the wrong way: every call resends the whole conversation.
- **Lower `TEH_EFFORT`** for routine work, and **`TEH_CONTEXT_WINDOW`** as a hard cap on conversation size.
- **Built in:**
  - files are edited with `teh-edit`, exact search-and-replace, instead of being rewritten (output costs about 5× input), and the model is told to combine related commands into one call
  - the model is told to read only what it needs rather than whole large files, to total and count data with scripts rather than by reading, not to repeat file contents or output in its replies, and to skip narration around tool calls
  - command output is cleaned of terminal codes, progress-bar redraws and repeated lines, then cut to `TEH_OUTPUT_LIMIT` characters, with the full output saved for `grep`
  - a command run again shows only what changed in its output
  - very long lines in command output are cut in the middle, with the full output saved
  - web pages arrive as excerpts, not whole pages

## How the code is organised

`teh.py` is one file in marked sections:
- **Shared** (top): the filter that makes text safe to show.
- **Part 1 · The harness:**
  - providers and their table (`PROVIDERS`, `PROVIDER_QUIRKS`)
  - settings (`Config`, fixed for the session) and state (`State`, what changes during it)
  - the environment: the shell, the scratch folder, the helpers' launchers (`HELPERS`), `AGENTS.md`, and the system prompt (`system_prompt()`)
  - the model API
  - commands
  - the conversation loop, budgets and compaction
  - chat input, `main()`, the startup segment, and the chat commands (`CHAT_COMMANDS`: to add one, write a function and add it there)
- **Part 2 · The web helper:** its settings, the rewrite table, HTML-to-text, `fetch_main()`, and search (the `WEB_SEARCH` table, `search_main()`).
- **Part 3 · The edit helper:** reading SEARCH/REPLACE blocks, applying them, `edit_main()`.
- **Entry point** (bottom): picks the role (`ROLES`; a new helper also needs a line in `HELPERS`, for its launcher).

Importing it has no side effects, so the unit tests can import it.

## Tests

```sh
tests/unix/run.sh              # every suite (about 30 seconds); Linux or macOS
tests/unix/run.sh core fetch   # some of them
tests/unix/run.sh --changed    # only the suites affected by what changed since they last passed
cd tests && python3 -m unittest test_units   # the unit tests alone, on any system
```

`tests/` holds what every system shares: the unit tests (`test_units.py`, plain Python) and the fake API servers (`fakes/`). Each system's own suites, which drive `teh` through its shell and terminal, live in a folder of their own: `tests/unix/` (bash, and a pseudo-terminal for chat) so far. See `tests/README.md` for the layout, and for adding Windows suites.

**`--changed`** skips a suite when nothing it depends on has changed since it last passed. That's `teh.py` (all of it for `core` and `fetch`, which test the web helper too; for the others, everything before Part 2), the suite's test script, the fake servers it starts, and the shared helpers. Comments don't count, so a comment-only edit reruns nothing; an edit to the web helper reruns `core` and `fetch` only. The unit tests always run, as they take under a second, and a failing one is shown in full. Each pass is recorded in `tests/unix/.passed` (delete it to start over). The dependencies are listed in `tests/unix/inputs.py`; a missing one could let a breaking change skip a suite, so run everything before you finish.

The suites wait for each fake server to accept connections, and for each prompt in chat tests, rather than for fixed times; the waits that remain are the deliberate ones (command timeouts, `retry-after`, a slow server).

The tests use fake API servers on your machine (`tests/fakes/`): no API key, no network, no cost. To measure what a change does with a real model, in tokens and in results, use the benchmark in `bench/` (see `bench/README.md`). The suites in `tests/unix/` need Linux or macOS (bash and a pseudo-terminal); the unit tests run anywhere.

| Suite | What it covers |
|---|---|
| `units` | Individual functions, the edit helper and search (with canned answers); that the source has no invisible characters or lines over 120 characters |
| `core` | Settings and their checks, the status line and context limit, shells, the Anthropic format, how commands run, `teh-edit` as the model runs it |
| `chat` | Approvals, Ctrl+C, refusals, the thinking timer, chat commands, `AGENTS.md`, scratch folder cleanup |
| `caching` | Each provider's caching behaviour, effort and auth headers |
| `errors` | Malformed tool calls, `retry-after` |
| `output` | Exit codes, `TEH_OUTPUT=json`, multi-line prompts |
| `compact` | Automatic compaction when the window is full, `/compact` in chat, the summary request, kept requests, the transcript, failures |
| `fetch` | The web helper, offline: text extraction, hidden-text removal, safety, JSON, word search, request options (headers, methods, bodies, API errors); search is covered by `units`, with canned API answers |

## License

`teh` is licensed under the [Mozilla Public License 2.0](LICENSE). You can use it in any project, open or closed; if you distribute a changed `teh.py`, its source (the changed file) stays under the MPL. The notice at the top of `teh.py` travels with the file when it's copied on its own.
