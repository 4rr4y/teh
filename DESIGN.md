# teh: design and internals

How `teh` works inside, and why it's built the way it is. For installing and using it, see the [README](README.md).

One fact drives most of the decisions here: every model call resends the whole conversation. So most of them keep the conversation small, or let the provider read it from its prompt cache, and every extra model call is avoided where it can be.

## How it saves tokens

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

## How commands run

- **In a new shell each time,** started in the directory where you launched `teh`, so `cd` and environment variables don't carry over. The shell gets your environment without `teh`'s own `TEH_` settings (see [Safety](README.md#safety)).
- **With no input:** a command that asks a question gets no answer and finishes at once, instead of hanging. The model is told to use options like `-y` and `git commit -m`.
- **Background jobs keep running:** `npm run dev &` returns at once and the server stays up.
- **Stopped after `TEH_COMMAND_TIMEOUT` seconds** (120 by default; `0` for no limit), with everything they started. The model still gets the output so far. Ctrl+C stops the running command too.
- **Stopped when the output passes 5,000,000 bytes,** so a runaway command (`yes`, a logging loop) can't fill the disk before the timeout. The model is told to write large output to a file and read only what it needs. Only output `teh` captures counts: a command writing to a file isn't limited. It's a constant in `teh.py`, `OUTPUT_MAX_BYTES`, rather than a setting.
- **Output:** normal and error output together, in order. What carries no information is removed first: terminal colour codes, the intermediate states of progress bars, and runs of identical lines (kept once, with a count, when the count is shorter). A line over 500 characters (minified code, a lockfile, base64) keeps its first and last 200, e.g. `[… 2,800 characters]` in between, so a few such lines can't push the rest of the output out; the full output is then saved, and the model told where. Output longer than `TEH_OUTPUT_LIMIT` (10,000 characters by default) is cut in the middle, at line breaks: the model sees the first and last lines, and a note saying how much was left out and where the **full output is saved** in the scratch folder, e.g. `[… 98,000 characters (17,000 lines) omitted; full output in /tmp/teh-…/output-1.txt: use grep or sed -n to read it]`. So the model can read any part of it with `grep` or `sed -n` instead of running the command again, which matters for slow, costly or one-off commands. Each result is resent on every later call, so keeping it short keeps the cost down.
- **Run again:** when the model runs a command it ran earlier in the conversation (the tests after a fix, `git status`, a build), it gets only what changed: `[the same output as the last time this command ran]`, or the changed lines as a diff, with a line around each change. The two are compared as they would be sent, and the changes are used only when under half as long as the output (a diff is harder to read). Otherwise the model gets the output as usual, and also when the earlier result is no longer in the conversation (after compaction or `/clear`), or when the output is over 100,000 characters.
- **Scratch folder:** each session gets a fresh folder in the system temp folder for temporary scripts, downloads and notes, and the model is told to use it rather than your project. The system prompt names it by its environment variable, `TEH_SCRATCH`, not its path, which is random (see [Prompt caching](#prompt-caching)). `teh` deletes it on exit, including when the terminal is closed or `teh` is stopped with `kill`. It's only left behind if `teh` is killed outright (`kill -9`, a crash), and probably when a Windows console window is closed.
- **Text encoding:** output is read as UTF-8; on Windows, output that isn't UTF-8 is read in the system's ANSI code page, which older programs still write. Piped input is read the same way, at most 5,000,000 bytes of it.
- **Refusals:** if the model or provider refuses, `teh` says so with the reason, and drops the refused prompt so you can carry on.

## Shells

Commands run in one shell, chosen at startup:
- **Linux and macOS:** `$SHELL`, or `/bin/sh` if that isn't set.
- **Windows:**
  - PowerShell if you started `teh` from PowerShell (`pwsh` when installed, else Windows PowerShell), otherwise cmd. Telling the two apart is a best guess (PowerShell adds a folder of its own to `PSModulePath`), so set `TEH_SHELL` to be sure.
  - Git Bash and MSYS2 set `$SHELL`, so they use bash.
- **Anywhere:** `TEH_SHELL` overrides the choice.

The model is told the OS and shell so it uses the right syntax, and the token-saving advice in the system prompt comes in that shell's own syntax (the `SHELL_EXAMPLES` table).

**On Windows**, both shells are tested on every push (`tests/e2e/`, as are bash and sh elsewhere):
- **cmd:** commands run as `cmd /d /s /c "…"`, as Python's `shell=True` does. A command line ends at its first line break, so a command of several lines would run only its first line and report that line's exit code: it runs as a batch file in the scratch folder instead, which runs every line and exits with the last one's code. A batch file reads `%` differently (a lone `%` is dropped, `%1` is an argument, an undefined `%NAME%` is empty, `for` loops need `%%i`), so `teh` doubles every `%` except in references to defined variables (`batch_percents()`), and each line means what it would on a command line: `100%`, `%20` in an address and a loop's `%i` all work as typed. The helpers are `.cmd` launchers.
- **PowerShell, every version from 1.0 to 7:** `teh` doesn't need PowerShell 7. It uses `pwsh` when that's installed, else the `powershell` that comes with Windows, and what it adds to each command is written to work in PowerShell 1.0 too (the oldest Windows that runs Python 3.10, Windows 8.1, comes with 4.0). Windows PowerShell 5.1 and PowerShell 7 are tested. A command reaches PowerShell in base64, so Windows' command-line quoting can't change it, and runs as a script block (`POWERSHELL_RUN`). Not `-EncodedCommand`, with which Windows PowerShell writes errors to a redirected stderr as CLIXML: errors come as plain text, and progress bars are switched off. The exit code is the failing program's own (`[exit 5]`), or 1 when a PowerShell command fails last; when a helper is the command's last statement, its exit code is used, as a PowerShell function always leaves `$?` true (a `;` or `|` inside a string, such as an address, doesn't end a statement). The system prompt's advice to run slow commands in parallel uses `Start-Job`, from PowerShell 2.0.
- **Non-English text:** while a command runs, `teh` switches the console to UTF-8 (and back afterwards), so cmd's and PowerShell's own output comes through whole, and has Python write UTF-8 too (`PYTHONIOENCODING`, unless you've set it). `teh`'s own output, when it goes to a file or a pipe, is UTF-8 too.

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
- **Files as they were:** Windows line endings (CRLF) are kept, and the blocks are matched against them. The blocks are read as UTF-8 (or, on Windows, the ANSI code page).
- **New files:** a single block with an empty SEARCH creates the file, and its folders.
- **`=======` lines in the text:** a Markdown or reStructuredText heading's underline, or a Git conflict, has the same line as the one between SEARCH and REPLACE. When a block has several, each could be the one that ends SEARCH, and the longest SEARCH that's found in the file wins. A shorter one would be found too (each starts the next), and taking it would write the rest of the real SEARCH into the file.

In PowerShell, the blocks are piped in with a here-string (`@'…'@ | teh-edit FILE`); in cmd, from a file (`teh-edit FILE < blocks.txt`). The system prompt describes the format in one sentence, about 25 tokens.

## Reading web pages

The model reads the web only through the helper; the system prompt rules out `curl`, `wget` and similar. The model runs it as `teh-fetch`: a tiny launcher for `teh.py --fetch` in the scratch folder, which is put first on the search path for its commands. A short name saves tokens in every call that uses it, and in the conversation afterwards. On Windows the launcher is a `.cmd` file. In PowerShell, which would drop the quotes around an address with `&` in it when running a `.cmd` file, `teh` instead adds a `teh-fetch` function to each command, so such addresses arrive intact. The helper writes UTF-8 whenever its output isn't a terminal, so non-English pages come through correctly on Windows too.

- **Text, not HTML:** scripts, styles, menus and page chrome are removed; headings, lists and code blocks are kept. Links become `[3]`, listed once at the end.
- **Only what's asked for:** with words, the lines containing any of them, numbered, with context; without, the start of the page. The full text is saved in the scratch folder, for `grep` or `sed`.
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

General web search engines don't work for a program that's honest about what it is. Tested from Python's standard library with the helper's own user agent: DuckDuckGo and Mojeek answer with a bot challenge, Brave with HTTP 429, and Google with a page that needs JavaScript. Bing answers, but with results unrelated to the query (for "python 3.14 release notes", pages about colonization for children), which is worse than no answer. So the helper searches sources that offer a free, official search API instead, with no key. The model runs searches like these:

```sh
teh-fetch --search wikipedia fusion energy
teh-fetch --search stackexchange:cooking sourdough starter     # SOURCE:OPTION, here a Stack Exchange site
teh-fetch --search github:issues tokio select cancel
teh-fetch --search                                              # every source, what it covers, and its limit
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

**Identifying yourself for higher limits:** some sources give clients with contact details in their user agent more room: Wikimedia 200 requests a minute instead of 10, Open Library 3 a second instead of 1; MusicBrainz and OpenStreetMap ask for it, and Crossref serves such clients from its "polite pool". `WEB_CONTACT`, at the top of the web helper in `teh.py`, is an email or a URL that those sites (only) get in the user agent `teh-fetch/0.1 (<contact>)` (teh's version, `__version__`); every other site keeps the anonymous user agent. It's set to `teh@teh.com` by default: replace it with your own email or URL, or set it to `""` to send nothing.

**Left out after testing:** Semantic Scholar, GDELT and Google Books (HTTP 429 on the first request), OpenAlex (its free budget is shared by everyone on your network and ran out at once), Europe PMC (14–31 seconds a search), Gutendex (25 seconds), Reddit and the Art Institute of Chicago (blocked), Open Food Facts (unavailable), TheMealDB (its free key is for development only).

**Adding a source:** one `SearchSource` entry in `WEB_SEARCH`: the API's URL (`{q}` the query, `{p}` the option), where the results are in its response, and short templates for each result's title, link and details (`{field}`, `{field[subfield]}`; a missing field is left out).

## Providers

The two API formats, Anthropic Messages and OpenAI chat completions, are each one class (`AnthropicFormat`, `OpenAIFormat`, in `FORMATS`). Each class builds the request, reads the reply into a `Reply`, writes tool definitions and results, and says where the effort level goes by default. To support another format, subclass `APIFormat` and add it to `FORMATS`.

How providers differ within a format is kept in one table in `teh.py`, `PROVIDER_QUIRKS`. Each entry is keyed by a fragment of the API URL and lists only what differs from the plain format. Every possible key is documented in `QUIRK_DEFAULTS`:

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

**Why `TEH_CONTEXT_WINDOW` should sit a little below the model's real limit:** compacting sends the whole conversation plus the summary request, so it needs some room.

## Budgets

Both budgets are checked before each model call, including a compaction call: the token budget adds what has been used to what the next call would resend (the conversation so far, and what was added since), so the run stops before the call that would go over, not after it. It's a token budget, not a cost budget: cached tokens cost about a tenth as much, but count in full, so a long chat reaches it sooner than its cost would suggest.

In chat, `/budget` changes either budget: `/budget tokens 2000000`, `/budget calls 50`, `/budget calls 0` (no limit), or `/budget off` for both. When a budget stops a turn, the commands that finished are kept in the conversation, so `continue` picks up where the model stopped rather than repeating the prompt, which would redo the work.

## Chat internals

- **`/undo`** removes only the end of the conversation, so everything before it is still read from the prompt cache, as after any finished turn: it never costs more than leaving the turn in. It doesn't undo what the turn's commands did (a changed file stays changed); it says how many commands ran. Prompts before a compaction (or `/clear`) can't be undone, since they're part of the summary.
- **Status line instead of confirmations:** commands that change something (`/model`, `/effort`, `/budget`, `/undo`, `/clear`) answer with the status line as it now stands, which shows the effort, the totals and token budget, the context and the call budget.
- **`/model`** checks the name against the models the provider lists (`GET /models`). A listed id switches at once; part of one, or nothing, lists the models whose ids contain it (or, for a typo, the closest), numbered with their context windows, to pick one by number. If the provider doesn't list its models, the switch goes ahead and an unknown name fails at the next call, with the provider's own error.
- **The context window follows the model:** after a switch it is the model's own window less `TEH_MAX_TOKENS` (a call must fit the conversation and the reply), larger or smaller than `TEH_CONTEXT_WINDOW`, which applies only when the provider doesn't give the model's window; `teh` says when it changes. A switch to a model whose window the conversation doesn't fit is refused, with a pointer to `/compact` (with the current model) or `/clear`: compacting after the switch would need the new model to read the whole conversation, which is what doesn't fit. There's no standard field for the window: the list's `max_input_tokens` (Anthropic), `context_length` (OpenRouter, Together), `context_window` (Groq) or `max_context_length` (Mistral), else it's unknown (OpenAI) and `TEH_CONTEXT_WINDOW` applies. OpenRouter, asked in the Anthropic format, lists Claude Code-style ids (`anthropic/<id>[1m]`): the `[1m]` only marks a window of 1M tokens or more, so it's dropped, and so is `anthropic/` where an id of the usual `vendor/model` form follows it (OpenRouter's own Claude ids, `anthropic/claude-…`, keep it). Models don't share a prompt cache, so after a switch the next call reads the whole conversation at full price: `teh` says so when there is a conversation to re-read. The API format (`TEH_FORMAT`) can't change mid-chat.
- **Pastes:** terminals that mark pastes are handled by readline, and for others `teh` joins lines that arrive at the same moment (on Windows, `msvcrt.kbhit`).

## Settings checks

At startup, `teh` warns about any `TEH_` variable it doesn't know, e.g. `unknown setting TEH_MODLE: did you mean TEH_MODEL?`, and stops with a clear message if a setting has a value it can't use: a number setting that isn't a whole number, an effort level it doesn't know, or a setting with fixed values (`TEH_AUTO`, `TEH_AGENTS_MD`, `TEH_FORMAT`, `TEH_OUTPUT`, `TEH_CACHE_RETENTION`) set to something else, e.g. `TEH_AUTO=true`. Those values may be in any case.

The chat's startup segment shows what `teh` found: OS, shell, working directory, the session's scratch folder, `AGENTS.md`, API, caching and model settings, the model's role, and any budgets.

## The status line

```
· anthropic · claude-opus-5-5 · medium · 12.4s · in 48,210 (45,900 cached) · out 1,204 · Σ 312,877 (241,350 cached) · ctx 49,414/262,144 (19%)
```

| Field | Meaning |
|---|---|
| `anthropic` | The provider: its shortcut name (also for a URL on the same server), else the URL's host (non-ASCII names in their `xn--` form, so lookalike letters stand out); `custom` for a server on this machine or a private network that isn't a known one, e.g. a llama.cpp server on `localhost:8080` |
| `claude-opus-5-5` · `medium` | The model that answered, and the effort (`default`: the provider's own) |
| `12.4s` | How long the reply took, including retries |
| `in` (`cached`) | Input tokens for this call: the whole conversation, resent every call. The cached part costs about a tenth as much |
| `out` | Output tokens for this reply |
| `Σ` (`cached`, `budget`) | Session totals, how much of them came from the cache, and `TEH_TOKEN_BUDGET` when one is set |
| `ctx` | Context used, out of the context window. When it passes half, `teh` suggests `/compact` once (it never compacts by itself before the window is full); it warns after every call from 80%, and compacts the conversation at 100% |
| `calls` | Model calls for this prompt out of `TEH_TURN_BUDGET`, e.g. `3/40 calls`, shown only when one is set |

Commands that change something (`/model`, `/effort`, `/budget`, `/undo`, `/clear`) answer with the status line as it now stands; on their own, `/effort` and `/budget` just show it (and `/model` too, when the provider doesn't list its models). While waiting, a live `· thinking… 7s` timer is shown, in a terminal only.

## One-shot results

With a task (or piped input), `teh` runs once and exits. The answer, the model's last reply, goes to stdout at the end; its earlier replies, status lines and commands go to stderr, so pipes get only the answer. Piped input is added to the task, cleaned of terminal codes; very long input is cut to fit, with the whole of it saved for the model to `grep`. Without a terminal there's nobody to approve commands, so unless `TEH_AUTO=1` is set the run stops with `no terminal to approve commands: set TEH_AUTO=1` (exit code 1).

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

Each command has its exit code; a command that was stopped (it timed out, or its output passed 5,000,000 bytes) has `"exit": null`, and a declined one has `"declined"` with the message the model was given. `error` says why a run that didn't finish ended.

More examples, in sh:

```sh
if TEH_AUTO=1 teh "check that the docs build without warnings" > report.txt; then
    echo "ok"
else
    echo "teh ended with exit code $?"
fi
TEH_OUTPUT=json TEH_AUTO=1 teh "update the changelog" | jq '.tokens, .commands'
for f in src/*.py; do                             # one run per file
    teh "suggest one improvement to this file" < "$f" > "reviews/$(basename "$f").md"
done
# crontab -e: every morning, a summary of yesterday's commits
0 8 * * * cd ~/project && TEH_AUTO=1 teh "summarise yesterday's commits for the team" > ~/summary.txt
```

## Windows

`teh` runs in cmd, Windows PowerShell and PowerShell 7. On Windows, `py teh.py` works too where the Python launcher is installed.

**A `teh` command.** cmd: a `teh.cmd` in a folder on `PATH`, here `%USERPROFILE%\bin` (run in the teh folder):

```bat
mkdir "%USERPROFILE%\bin" 2>nul & echo @python "%CD%\teh.py" %*> "%USERPROFILE%\bin\teh.cmd"
```

PowerShell: a function in your profile, loaded by every new PowerShell window (run in the teh folder):

```powershell
New-Item -ItemType Directory -Force (Split-Path $PROFILE) | Out-Null
Add-Content $PROFILE '$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false'
$line = 'function teh { $in = @($input); if ($in.Count) { $in | python "TEH" $args } else { python "TEH" $args } }'
Add-Content $PROFILE $line.Replace("TEH", "$PWD\teh.py")
```

The function passes on what's piped to it (`git diff | teh "review this"`) only when there is something, so `teh` on its own still chats in the console. The first line makes text piped to and from programs UTF-8, so non-English text survives `git diff | teh` and `teh … | Set-Content` (Windows PowerShell's defaults are ASCII and the console's old code page; PowerShell 7's still the latter). It works in every version, 1.0 to 7. Windows PowerShell doesn't load profiles until scripts are allowed for your user: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Without the profile, run these lines in each new window instead.

**Scripts and pipelines,** cmd. Settings are set for the rest of the session, as cmd has no way to set one for a single command:

```bat
git diff | teh "review this change"
git diff --staged | teh "write a commit message" > msg.txt
type error.log | teh "explain this error" | more
teh "summarise this file in 3 lines" < notes.txt
set "TEH_AUTO=1" & teh "run the tests and fix any failures" & set "TEH_AUTO="
call teh "check that the docs build without warnings" > report.txt
if errorlevel 1 (echo teh ended with exit code %errorlevel%) else (echo ok)
rem one run per file (in a .cmd file, write %%f instead of %f)
for %f in (src\*.py) do @teh "suggest one improvement to this file" < "%f" > "reviews\%~nf.md"
```

PowerShell, with the `teh` function and its UTF-8 line (these work in Windows PowerShell 5.1 and PowerShell 7; avoid `"` inside a prompt, which Windows PowerShell drops from a program's arguments, a bug fixed in PowerShell 7.3):

```powershell
git diff | teh "review this change"
git diff --staged | teh "write a commit message" | Set-Content msg.txt    # > writes UTF-16 in Windows PowerShell
Get-Content -Encoding UTF8 error.log | teh "explain this error" | more
Get-Content -Encoding UTF8 notes.txt | teh "summarise this file in 3 lines"   # PowerShell has no < for input
$env:TEH_AUTO = "1"; teh "run the tests and fix any failures"; Remove-Item env:TEH_AUTO
teh "check that the docs build without warnings" | Set-Content report.txt
if ($LASTEXITCODE -eq 0) { "ok" } else { "teh ended with exit code $LASTEXITCODE" }
$env:TEH_OUTPUT = "json"
(teh "how many Python files are here?" | ConvertFrom-Json).answer     # ConvertFrom-Json: PowerShell 3.0 and later
$env:TEH_OUTPUT = $null
```

Windows PowerShell's `Get-Content` reads a file without a byte-order mark in the ANSI code page, so `-Encoding UTF8` keeps UTF-8 files' non-English text whole (PowerShell 7 reads UTF-8 by default). Its `Set-Content` writes the ANSI code page; add `-Encoding UTF8` for UTF-8 there too.

**Several setups.** cmd: a `.cmd` file per setup, in a folder on `PATH`; `setlocal` keeps its settings from leaking into your session:

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

**A scheduled run:** put the run in a `.cmd` file, with its settings, and schedule that (from cmd or PowerShell):

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

## Safety details

- **The approval prompt is the main safeguard.** With `TEH_AUTO=1` (or `a`), commands run unseen, and since the model reads web pages, a page could try to steer it. The web helper can send data (`-d`, `--json`, any `-X` method) as well as read pages, so check what a `teh-fetch` command sends, and where, before approving it.
- **Text from the web:** the helper leaves out hidden elements (`hidden`, `aria-hidden`, `display:none`, `visibility:hidden`); text hidden by a page's stylesheets can't be detected this way. It labels its output as data, and the model is told never to follow instructions found in it.
- **Hidden characters:** control characters and invisible or direction-changing Unicode are removed from web text. They're also shown as a visible `�` in the model's answers, its reasoning and the commands you approve, so a command can't look different from what it is.
- **`AGENTS.md`** is read from the project root down to the working directory, never from above the project root or your home folder (see [AGENTS.md](#agentsmd)). It's loaded whenever present, so use `TEH_AGENTS_MD=0` in projects you don't trust, and keep your own short: it's sent with every call.
- **The model's commands don't see `teh`'s settings.** Every `TEH_` variable, `TEH_API_KEY` included, is removed from their environment. The one they get is `TEH_SCRATCH`, the scratch folder's path, which `teh` sets itself for the web helper. The rest of your environment is passed on unchanged, so a key you've exported under another name (e.g. `ANTHROPIC_API_KEY`) is still visible to them.

## How the code is organised

`teh.py` is one file in marked sections:
- **Shared** (top): the filter that makes text safe to show, and the decoding of command output and piped input.
- **Part 1 · The harness:**
  - providers and their table (`PROVIDERS`, `PROVIDER_QUIRKS`)
  - the settings table (`SETTINGS`: one row per `TEH_` variable, saying how it's read, which field it sets and its `--help` line; to add a setting, add a row and document it in the README)
  - the session (`Session`): the settings (`Config`, fixed at startup), what was found and set up at startup (`Environment`: the shell, the scratch folder, the system prompt), what changes during the session (`State`: the model, effort, totals and budgets) and during one prompt (`TurnState`), and the conversation. There's no global state: every function that needs any of it is given the session
  - the environment: the shell, the scratch folder, the helpers' launchers (`HELPERS`), how PowerShell commands run (`POWERSHELL_RUN`), `AGENTS.md`, and the system prompt (`system_prompt()`)
  - the model API: one class per format (`FORMATS`), and `step()`, which makes one call and returns a `Reply` (text, reasoning, tool calls and `Usage`)
  - commands
  - the conversation loop, budgets and compaction
  - chat input, `main()`, the startup segment, and the chat commands (`CHAT_COMMANDS`: to add one, write a function and add it there)
- **Part 2 · The web helper:** its settings, the rewrite table, HTML-to-text, `fetch_main()`, and search (the `WEB_SEARCH` table, `search_main()`).
- **Part 3 · The edit helper:** reading SEARCH/REPLACE blocks, applying them, `edit_main()`.
- **Entry point** (bottom): picks the role (`ROLES`; a new helper also needs a line in `HELPERS`, for its launcher).

Importing it has no side effects, so the unit tests can import it.

## Tests

The tests use fake API servers on your machine (`tests/fakes/`): no API key, no network, no cost. `tests/` holds the unit tests (`test_units.py`) and the fake servers, and `tests/e2e/` the suites that drive `teh` through its shells and terminal. All are plain Python, and the same suites run on every system: what differs between systems (the shells and their syntax, Ctrl+C, running without a terminal, listing processes) is kept in `tests/e2e/lib.py`, so each suite says what it checks once. They run the model's commands in bash and sh (and zsh where it's installed), or in cmd, Windows PowerShell and PowerShell 7 where it's installed. See [`tests/README.md`](tests/README.md) for the layout. GitHub Actions runs them on Linux and Windows on every push and pull request, with Python 3.10, 3.12 and 3.14 (`.github/workflows/tests.yml`).

| Suite | What it covers |
|---|---|
| `units` | Individual functions, the edit helper and search (with canned answers); that the source has no invisible characters or lines over 120 characters |
| `core` | Settings and their checks, the status line and context limit, shells, the Anthropic format, how commands run, `teh-edit` as the model runs it |
| `chat` | Approvals, Ctrl+C, refusals, the thinking timer, chat commands, `AGENTS.md`, scratch folder cleanup |
| `caching` | Each provider's caching behaviour, effort and auth headers |
| `errors` | Malformed tool calls, `retry-after` |
| `output` | Exit codes, `TEH_OUTPUT=json`, multi-line prompts, piped input and non-English text in and out |
| `compact` | Automatic compaction when the window is full, `/compact` in chat, the summary request, kept requests, the transcript, failures |
| `fetch` | The web helper, offline: text extraction, hidden-text removal, safety, JSON, word search, request options (headers, methods, bodies, API errors); search is covered by `units`, with canned API answers |

**`--changed`** skips a suite when nothing it depends on has changed since it last passed. That's `teh.py` (all of it for `core` and `fetch`, which test the web helper too; for the others, everything before Part 2), the suite's test script, the fake servers it starts, and the shared helpers. Comments don't count, so a comment-only edit reruns nothing; an edit to the web helper reruns `core` and `fetch` only. The unit tests always run, as they take seconds, and a failing one is shown in full. Each pass is recorded in `tests/e2e/.passed` (delete it to start over). The dependencies are listed in `tests/e2e/inputs.py`; a missing one could let a breaking change skip a suite, so run everything before you finish.

The suites wait for each fake server to accept connections, and for each prompt in chat tests, rather than for fixed times; the waits that remain are the deliberate ones (command timeouts, `retry-after`, a slow server).

To measure what a change does with a real model, in tokens and in results, use the benchmark in `bench/` (see [`bench/README.md`](bench/README.md)).

### Running them

They need only Python, and run the same way on Linux, macOS and Windows (use `python3` where `python` is Python 2, and `\` in paths on Windows):

```sh
python tests/e2e/run.py              # every suite (about a minute)
python tests/e2e/run.py core fetch   # some of them
python tests/e2e/run.py --changed    # only the suites affected by what changed since they last passed
cd tests && python -m unittest test_units   # the unit tests alone
```

### Linting (for development only)

You don't need ruff, or anything in `requirements-dev.txt`, to use `teh`: it still needs nothing but Python. The code is checked with [ruff](https://docs.astral.sh/ruff/), with the rules in `ruff.toml`: the same check locally and in CI, at the version pinned in `requirements-dev.txt`.

```sh
pip install -r requirements-dev.txt   # once: development tools only, not needed to use teh
ruff check                            # lint, from the repository's root
git config core.hooksPath .githooks   # once per clone: lint and unit tests before every push
```

With the hook on, a push that would fail the lint check or the unit tests stops before it leaves (`git push --no-verify` pushes anyway).
