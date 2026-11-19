# teh benchmark

Measures what a change to teh costs in tokens, and what it does to results, on 27 everyday tasks: 13 a developer would
give an agent, and 14 anyone might (files, spreadsheets, documents, logs, questions). Five of them (`xl_*`) are big
on purpose: they make the model read or write a lot over many calls, to reach the context sizes where compaction
acts. Each task is checked
automatically, so a change that saves tokens but breaks tasks shows up as fewer passes, not as a saving.

```sh
export TEH_BASE_URL=anthropic TEH_MODEL=claude-opus-5-5 TEH_API_KEY=$(cat ~/.keys/anthropic)
bench/run.py                                   # every task once, teh as it is; results in bench/results/<date>/
bench/run.py --repeat 3 --name base            # three runs of each: models vary from run to run
bench/run.py --tasks multi_bug api_migration   # some tasks (names or patterns, e.g. 'web_*')
bench/run.py --config baseline --config compact20k TEH_CONTEXT_WINDOW=20000 --tasks 'xl_*' --repeat 5 --name xl
bench/report.py bench/results/xl --tasks       # the summary again, and each task against the baseline
bench/simulate.py bench/results/base           # compaction thresholds, replayed on recorded runs
bench/run.py --config new --config old HARNESS=/path/to/old/teh.py --name ab   # two versions of teh, same day
bench/selftest.py                              # checks the tasks' own checkers, without a model (no cost)
```

**Safety:** the runs use `TEH_AUTO=1`, so the model's commands run without asking. Each task runs in a fresh folder
in the temp folder, but commands can reach the rest of the machine, so run the benchmark in a VM or container you
don't mind changing. The three web tasks (`web_*`) are left out unless you pass `--web` or name them: they depend on
the sites staying as they are.

## The tasks

| Task | Kind | Size | What it asks |
|---|---|---|---|
| `access_log` | everyday | long | the worst hour and the worst client in a 60,000-line web server log |
| `bank_budget` | everyday | long | combine three bank statements in different formats into spending by month and category |
| `dedupe_contacts` | everyday | short | remove duplicate contacts that differ in case, spaces and phone format |
| `invoice_rename` | everyday | short | rename 20 invoices by date and vendor (four date formats), and total them |
| `mail_merge` | everyday | short | one letter per person from a template and a CSV |
| `meetings_ics` | everyday | short | a calendar file from meeting notes written in prose |
| `policy_lookup` | everyday | short | one fact buried in a 40-file staff handbook, with a decoy |
| `sales_report` | everyday | short | the best region's Q3 revenue from a year of sales |
| `sort_photos` | everyday | short | sort photos into year/month folders by the dates in their names |
| `tos_changes` | everyday | long | which sections changed between two versions of 48-section terms of service |
| `api_migration` | dev | long | move 8 modules to a library's new API, from its changelog |
| `bash_backup` | dev | short | fix a shell script that breaks on names with spaces |
| `cli_top_flag` | dev | short | add an option to a command-line tool |
| `config_trace` | dev | short | which port a service really uses, through four layers of config (and a trap) |
| `crash_from_log` | dev | long | find a crash in a 26,000-line log and fix its cause |
| `fix_pagination` | dev | short | fix two bugs so the tests pass |
| `js_duration` | dev | short | fix two bugs in a JavaScript module (needs `node`) |
| `multi_bug` | dev | long | fix 4 bugs in 4 modules of a 9-module package, from 8 failing tests |
| `rename_symbol` | dev | short | rename a function in code, tests and docs, but not a similar name |
| `sqlite_query` | dev | short | an SQL query over three tables |
| `web_wiki_fact`, `web_pypi_license`, `web_stackoverflow` | both | short | facts from Wikipedia, PyPI and Stack Overflow, through `teh-fetch` |
| `slow_tests` | dev | slow | run two test suites of about half a minute each, and say which tests fail |
| `slow_reports` | everyday | slow | build three reports with a script that takes about half a minute each, and say which region sold most |
| `xl_meeting_actions` | everyday | xl | the current owner, due date and status of every action item, from 26 weeks of meeting notes (about 20,000 words) |
| `xl_contracts` | everyday | xl | which of 20 supplier contracts need notice of non-renewal this quarter, by when, and at what fee, with amendments and letters |
| `xl_expense_audit` | everyday | xl | every claim among 773 that breaks a 14-section expenses policy (with dated changes and exceptions) |
| `xl_lang_bugs` | dev | xl | fix 5 bugs in a 900-line interpreter for a small scripting language |
| `xl_lang_feature` | dev | xl | add `for` loops, `break` and `continue` to that interpreter, from a spec: lexer, parser, interpreter and formatter |

The two `xl_lang_*` tasks share the interpreter in `tasks/_minilang/`, correct as it is; `xl_lang_bugs` plants its bugs
when it sets up.

Each task is one file in `tasks/` (see `tasks/_lib.py` for the format). Its data is generated from a fixed seed, so
every run sees the same files. Its check is never shown to the model, and checks the result, not the method: a
developer task also runs hidden tests, so a fix that only satisfies the visible tests fails. After adding or
changing a task, run `bench/selftest.py`: for every task, doing nothing must fail and a reference solution must pass.

## What's measured

Every model call passes through a small proxy on localhost that records its token usage, including cache writes and
reads (teh's own JSON summary doesn't separate them), so the report can weigh them as the provider charges:

- **cost**: input-token equivalents, `uncached + 1.25 × cache writes + 0.1 × cache reads + 5 × output` by default.
  Set `--write`, `--read` and `--output` in `report.py` to your model's price ratios.
- **pass**: the share of runs whose check passed, with a 90% range. With a few runs per task, a difference inside
  the range may be noise: use `--repeat` (3 at least, 5 for decisions).
- calls, input, cached share, output and peak context per run.

Each run also keeps teh's log (`logs/`, everything it printed) and the trace of its calls (`traces/`). A run is a
line in `results.jsonl`; running again with the same `--name` skips finished runs, so an interrupted benchmark resumes
where it stopped.

The two `slow_*` tasks have steps that take about half a minute each and don't depend on each other, for what running commands in parallel saves; the other tasks' commands are quick.

A config can name another copy of teh with `HARNESS=path`, so two versions (a prompt change, say) run side by side on the same day: comparing against results from another day mixes in whatever changed at the provider.

Guards: each run stops at 80 model calls (150 for xl tasks; `TEH_TURN_BUDGET`) or 4,000,000 tokens
(`TEH_TOKEN_BUDGET`), and after 10 minutes (25 for long tasks, 45 for xl). A config can change the first two.

## Evaluating a change: compaction thresholds as the example

1. **Baseline**, with traces for the replay: `bench/run.py --tasks 'xl_*' --repeat 3 --name xl`. Look at the peak
   contexts in the report: they decide which thresholds are worth testing, since compaction only acts above them.
2. **Replay** the baseline's traces at lower thresholds (`bench/simulate.py bench/results/xl`). It costs nothing, but
   treat it as a rough guide: it depends on how much the model reads again after compacting, which it can only
   guess. On the xl tasks the model read back almost nothing, so the real saving matched the "reread 0" column.
3. **Real runs** at the promising thresholds, against the baseline: `--config compact20k TEH_CONTEXT_WINDOW=20000`
   and so on. A smaller window also lowers the cap on command output teh keeps (twice the window, in characters),
   so check that no output came near it. A change is a gain only if cost falls and the pass rate doesn't.

Clearing old command outputs (an experimental `TEH_CLEAR_AT`) was tried this way and removed: at 25,000 tokens it saved
nothing measurable, and at 15,000 it cost 45% more and failed a task, because the model read back what was cleared and
every clearing rewrites the prompt cache.
