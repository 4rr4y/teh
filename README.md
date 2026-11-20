# teh

**t**oken **e**fficient **h**arness: a minimal LLM harness.

## Why teh

- **No Additional Depedencies** - Provisioned as a single Python file.
- **Token Efficient** - Aims to replicate token-efficient mechanisms where applicable. Compact on demand.
- **One Tool** - Terminal/Shell access only. No skills. No MCP. Still reads AGENTS.md for projects.
- **Built-in Web Fetch** - Built-in web fetch capability and use of known search APIs.
- **Token Usage** - Easy-to-see token usage statistics.
- **Pipeline** - Ability to be used in CLI as part of a pipeline.

More details in [DESIGN.md](DESIGN.md).

## Install

1. Install Python 3.10 or later. On macOS, if it's from python.org, also run `Install Certificates.command` in its folder under `/Applications`, or teh can't connect.
2. Download `teh.py` from the [latest release](https://github.com/4rr4y/teh/releases/latest)
3. `python3 teh.py` (on Windows, `python teh.py`). Or clone the repository:

```sh
git clone https://github.com/4rr4y/teh && cd teh
```

## Quick start

Set a provider, a model and your key, then run it. This uses DeepSeek V4.1 Flash through OpenCode Go:

```sh
# sh
export TEH_BASE_URL=opencode-go TEH_MODEL=deepseek-v4.1-flash TEH_API_KEY="<your key>"
python3 teh.py
```

```bat
rem Windows, cmd
set "TEH_BASE_URL=opencode-go" & set "TEH_MODEL=deepseek-v4.1-flash" & set "TEH_API_KEY=<your key>"
python teh.py
```

```powershell
# Windows, PowerShell
$env:TEH_BASE_URL = "opencode-go"; $env:TEH_MODEL = "deepseek-v4.1-flash"; $env:TEH_API_KEY = "<your key>"
python teh.py
```

`TEH_BASE_URL` is a [provider name](#providers) or any API URL. The settings last until the terminal is closed; all of them are in [Settings](#settings).

To type `teh` from any folder instead of `python3 teh.py` (sh, bash, zsh; `~/.local/bin` must be on `PATH`):

```sh
chmod +x teh.py && ln -s "$PWD/teh.py" ~/.local/bin/teh
```

For cmd and PowerShell, see [Windows](DESIGN.md#windows). The examples below use `teh`.

## Example Interactive Mode Chat

```
$ teh
> why does make fail?
· anthropic · claude-opus-5-5 · default · 2.8s · in 2,301 · out 64 · Σ 2,365 · ctx 2,365/262,144 (1%)

$ make 2>&1 | tail -15
run? [y]es · [a]ll · [N]o, or type what to do instead: y

The linker can't find libssl. Install it with `sudo apt install libssl-dev`, then run make again.
· anthropic · claude-opus-5-5 · default · 3.4s · in 2,980 (2,301 cached) · out 41 · Σ 5,386 (2,301 cached) · ctx 3,021/262,144 (1%)
```

## Basic Commands

| Command | What it does |
|---|---|
| `/model [id or part of one]` | Switch model. Part of an id, or nothing, lists the provider's models with their context windows, to pick one |
| `/effort <level\|off>` | Change the reasoning effort |
| `/budget [tokens N \| calls N \| off]` | Change the [budgets](DESIGN.md#budgets) (`0` = no limit) |
| `/compact [what to keep]` | Summarise the conversation, and go on |
| `/undo` | Remove the last prompt and what followed it. A changed file stays changed |
| `/clear` | Start a new conversation |
| `/help` | Show all options |
| `/quit` | Exit |

To save tokens: `/clear` between unrelated tasks, `/compact` in long ones, `/undo` after a turn that went the wrong way, and a lower `/effort` for routine work.

## Settings

All settings are environment variables. Only the first two are required.

| Variable | Default | Meaning |
|---|---|---|
| `TEH_BASE_URL` | required | A [provider name](#providers) or any API URL |
| `TEH_MODEL` | required | Model id; `/model` changes it in chat |
| `TEH_API_KEY` | none | API key for the provider; not needed for local servers |
| `TEH_EFFORT` | provider default | Reasoning effort: `none`, `minimal`, `low`, `medium`, `high`, `xhigh` or `max` (which work depends on the model) |
| `TEH_AUTO` | off | `1` runs commands without asking |
| `TEH_MAX_TOKENS` | `16000` | Max output tokens per reply |
| `TEH_CONTEXT_WINDOW` | `262144` | Context size at which the conversation is summarised. Keep it a little below the model's limit; local models often need e.g. `32000`. `/model` sets it from the provider's list when it can |
| `TEH_THINKING` | `0` (hidden) | Show the model's reasoning, up to this many characters |
| `TEH_FORMAT` | from the URL | `anthropic` or `openai` API format |
| `TEH_OUTPUT` | text | `json` prints one-shot results as one JSON object |
| `TEH_AGENTS_MD` | on | `0` stops reading the project's `AGENTS.md` files |
| `TEH_CACHE_RETENTION` | provider default | `long` keeps the prompt cache longer (Anthropic 1 hour, OpenAI 24 hours); costs more, worth it for chat with long pauses |
| `TEH_ROLE` | a helpful assistant | Who the model is, e.g. `a senior Go developer reviewing for concurrency bugs` |
| `TEH_COMMAND_TIMEOUT` | `120` | Seconds before a command is stopped (`0` = no limit) |
| `TEH_OUTPUT_LIMIT` | `10000` | Characters of a command's output the model sees; the rest is saved for it to search |
| `TEH_TOKEN_BUDGET` | `0` (no limit) | Number of tokens the whole run may use |
| `TEH_TURN_BUDGET` | `0` (no limit) | Number of model calls for one prompt |
| `TEH_SHELL` | the shell you're in | Shell to run commands in: `bash`, `zsh`, `sh`, `pwsh`, `powershell`, `cmd`, … |

A misspelt setting gets a warning with a suggestion (`TEH_MODLE: did you mean TEH_MODEL?`), and a value `teh` can't use stops it with a clear message.

## Providers

`TEH_BASE_URL` accepts these names as abbreviations, or any OpenAI-compatible or Anthropic API URL:

`anthropic` `openai` `openrouter` `opencode` `opencode-go` `mistral` `deepseek` `groq` `gemini` `xai` `nanogpt` `nanogpt-sub` `venice` `together` `fireworks` `cerebras` `moonshot` `zai` `minimax` `qwen` `cohere` `huggingface` `deepinfra` `sambanova` `nebius` `novita` `chutes` `featherless` `ollama` `lmstudio`

- `ollama` and `lmstudio` run on your own machine and need no key.
- The API format is Anthropic's when the URL contains "anthropic", otherwise OpenAI's; `TEH_FORMAT` overrides it.

## Scripts and pipelines

With a task, or piped input, `teh` runs once and prints only the answer, so it works in pipes:

```sh
teh "what's using the most disk space here?"
git diff | teh "review this change"
git diff --staged | teh "write a commit message" > msg.txt
teh "summarise this file in 3 lines" < notes.txt
TEH_AUTO=1 teh "run the tests and fix any failures"            # no approval prompts, for this run
TEH_OUTPUT=json TEH_AUTO=1 teh "how many Python files are here?" | jq -r .answer
```

Without a terminal (CI, cron), set `TEH_AUTO=1`: nobody can approve commands. The exit code says how the run ended: 0 done, 1 error, 2 refused, 3 context full, 4 reply cut off, 5 budget reached, 130 cancelled. `TEH_OUTPUT=json` prints the whole result as one JSON object; both are described in [One-shot results](DESIGN.md#one-shot-results), and the cmd and PowerShell versions of these examples in [Windows](DESIGN.md#windows).

To keep several setups, give each a short command, e.g. in `~/.bashrc`:

```sh
alias teh-claude='TEH_BASE_URL=anthropic TEH_MODEL=claude-opus-5-5 TEH_API_KEY=$(cat ~/.keys/anthropic) teh'
alias teh-local='TEH_BASE_URL=ollama TEH_MODEL=qwen3 TEH_CONTEXT_WINDOW=32000 teh'   # on your machine, no key
```

## Safety

- **The approval prompt is the main safeguard.** - With `TEH_AUTO=1` (or `a`), commands run unseen, and can be steered by web fetch results.
- **Web text referred as data:** - Hidden text and invisible characters are removed. Model is prompted to treat web responses data.
- **`AGENTS.md` is read whenever present:** use `TEH_AGENTS_MD=0` in projects you don't trust.

More in [Safety details](DESIGN.md#safety-details).

## Acknowledgements

- teh c kosong peng (favourite drink)

## License

`teh` is licensed under the [Mozilla Public License 2.0](LICENSE). You can use it in any project, open or closed; if you distribute a changed `teh.py`, its source (the changed file) stays under the MPL. The notice at the top of `teh.py` travels with the file when it's copied on its own.
