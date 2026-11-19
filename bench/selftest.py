#!/usr/bin/env python3
"""Checks the benchmark's tasks themselves, without a model: for each task, doing nothing must fail its check, and a
reference solution must pass it. Run it after adding or changing a task: python3 bench/selftest.py [task ...]"""
import csv, difflib, io, json, re, shutil, sys, tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "tasks"))
from run import load_tasks  # noqa: E402


def text(d, name, content):
    Path(d, name).parent.mkdir(parents=True, exist_ok=True)
    Path(d, name).write_text(content)


# ===== Reference solutions: (folder) -> the final answer; they change files like the model would ====================
def sales_report(d):
    totals = Counter()
    for row in csv.DictReader(open(d / "sales.csv")):
        if "2025-07" <= row["date"][:7] <= "2025-09":
            totals[row["region"]] += int(row["units"]) * float(row["unit_price"])
    region, total = totals.most_common(1)[0]
    return f"{region}, with ${total:,.0f} in Q3."

def sort_photos(d):
    for f in list((d / "photos").iterdir()):
        if f.name == "notes.txt" or f.is_dir():
            continue
        m = re.search(r"(20\d\d)-?(\d\d)-?\d\d", f.name)
        target = d / "photos" / (f"{m[1]}/{m[2]}" if m else "unsorted")
        target.mkdir(parents=True, exist_ok=True)
        f.rename(target / f.name)
    return "Done."

def access_log(d):
    hours, ips = Counter(), Counter()
    for line in open(d / "access.log"):
        m = re.match(r'(\S+) .*?\[(\d\d)/(\w\w\w)/(\d{4}):(\d\d).*?" (\d{3}) ', line)
        if int(m[6]) >= 500:
            hours[f"{m[4]}-{m[3]}-{m[2]} {m[5]}:00"] += 1
            ips[m[1]] += 1
    (hour, n), (ip, _) = hours.most_common(1)[0], ips.most_common(1)[0]
    when = datetime.strptime(hour, "%Y-%b-%d %H:%M")
    text(d, "incident.md", f"# Incident\n\nWorst hour: {when:%Y-%m-%d %H:%M} UTC, {n} 5xx responses.\n"
                           f"Top client by 5xx: {ip}.\n")
    return "Written incident.md"

def meetings_ics(d):
    events = [("Kickoff with Dana", "20261207T093000", "20261207T103000", "Room 4"),
              ("Budget review", "20261209T140000", "", ""),
              ("Team lunch", "20261211T121500", "20261211T131500", "Teh Tarik Cafe\\, Bencoolen St")]
    body = "".join(f"BEGIN:VEVENT\r\nUID:{i}@x\r\nSUMMARY:{s}\r\nDTSTART:{a}\r\n"
                   + (f"DTEND:{b}\r\n" if b else "DURATION:PT1H30M\r\n") + (f"LOCATION:{loc}\r\n" if loc else "")
                   + "END:VEVENT\r\n" for i, (s, a, b, loc) in enumerate(events))
    text(d, "meetings.ics", f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//x//EN\r\n{body}END:VCALENDAR\r\n")
    return "Created meetings.ics"

def bank_budget(d):
    rules = [line.split("=") for line in open(d / "categories.txt") if "=" in line and not line.startswith("#")]
    rules = [(k.strip().lower(), v.strip()) for k, v in rules]
    spend = []  # (date, description, amount spent)
    for row in csv.DictReader(open(d / "bank_a.csv")):
        spend.append((datetime.strptime(row["Date"], "%d/%m/%Y"), row["Description"], -float(row["Amount"])))
    for row in csv.DictReader(open(d / "bank_b.csv"), delimiter=";"):
        if row["debit"]:
            spend.append((datetime.strptime(row["date"], "%Y-%m-%d"), row["payee"],
                          float(row["debit"].replace(",", "."))))
    for line in open(d / "card_c.txt"):
        m = re.match(r"(\d\d \w\w\w \d\d)\s{2,}(.+?)\s{2,}(-?[\d.]+)$", line.rstrip())
        if m:
            spend.append((datetime.strptime(m[1].title(), "%d %b %y"), m[2], float(m[3])))
    totals = Counter()
    for when, desc, amount in spend:
        if amount <= 0 or "TRANSFER" in desc:
            continue
        category = next((c for k, c in rules if k in desc.lower()), "Other")
        totals[(f"{when:%Y-%m}", category)] += amount
    rows = [f"{m},{c},{t:.2f}" for (m, c), t in sorted(totals.items())]
    text(d, "summary.csv", "month,category,total\n" + "\n".join(rows) + "\n")
    return "Written summary.csv"

def dedupe_contacts(d):
    rows, seen, out = list(csv.reader(open(d / "contacts.csv"))), set(), []
    for row in rows[1:]:
        key = row[1].strip().lower()
        if key not in seen:
            seen.add(key)
            out.append([row[0].strip(), key, row[2], row[3]])
    with open(d / "contacts_clean.csv", "w", newline="") as f:
        csv.writer(f).writerows([rows[0]] + out)
    return f"{len(out)} people"

def policy_lookup(d):
    return "45 days after you return (handbook/travel.md)."

def mail_merge(d):
    template = (d / "template.txt").read_text()
    for p in csv.DictReader(open(d / "people.csv")):
        if p["status"] != "declined":
            letter = template
            for field, column in (("First name", "first_name"), ("Event", "event"), ("Date", "date"),
                                  ("Venue", "venue"), ("Ticket", "ticket")):
                letter = letter.replace(f"[{field}]", p[column])
            text(d, f"letters/{p['first_name']}_{p['last_name']}".lower().replace(" ", "-") + ".txt", letter)
    return "Done"

def tos_changes(d):
    def parse(name):
        parts = re.split(r"^§ (\d+)  (.*)$", (d / name).read_text(), flags=re.M)
        return {int(parts[i]): (parts[i + 1], parts[i + 2]) for i in range(1, len(parts), 3)}
    a, b = parse("terms_v1.txt"), parse("terms_v2.txt")
    lines = []
    for n in sorted(set(a) | set(b)):
        if n not in b:
            lines.append(f"- § {n} {a[n][0]}: removed")
        elif n not in a:
            lines.append(f"- § {n} {b[n][0]}: added")
        elif a[n] != b[n]:
            lines.append(f"- § {n} {a[n][0]}: changed")
    text(d, "changes.md", "\n".join(lines) + "\n")
    return "Written changes.md"

def invoice_rename(d):
    total = 0.0
    for f in sorted((d / "invoices").glob("scan*.txt")):
        lines = f.read_text().splitlines()
        vendor = lines[0].strip().lower().replace(" ", "-")
        raw = next(line for line in lines if line.startswith("Date:"))[5:].strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%b %d, %Y"):
            try:
                when = datetime.strptime(raw, fmt)
                break
            except ValueError:
                pass
        due = next(line for line in lines if re.match(r"(Total due|AMOUNT DUE|TOTAL|Please pay)", line))
        total += float(re.search(r"(\d+\.\d\d)", due)[1])
        f.rename(f.with_name(f"{when:%Y-%m-%d}_{vendor}.txt"))
    text(d, "invoices/total.txt", f"{total:.2f}\n")
    return "Done"

def fix_pagination(d):
    p = d / "pagination.py"
    p.write_text(p.read_text().replace("pages = len(items) // per_page", "pages = max(1, -(-len(items) // per_page))")
                 .replace("start = page * per_page", "start = (page - 1) * per_page"))
    return "Fixed"

def cli_top_flag(d):
    p = d / "wordcount.py"
    p.write_text(p.read_text().replace('    parser.add_argument("file")\n',
                                       '    parser.add_argument("file")\n    parser.add_argument("--top", type=int)\n')
                 .replace('different")\n', 'different")\n    if args.top:\n        for word, n in sorted(counts.items(), '
                          'key=lambda x: (-x[1], x[0]))[:args.top]:\n            print(word, n)\n'))
    return "Added"

def js_duration(d):
    p = d / "duration.js"
    p.write_text(p.read_text().replace("seconds = seconds - n;", "seconds -= n * size;").replace("[hms]", "[dhms]"))
    return "Fixed"

def bash_backup(d):
    text(d, "backup.sh", '#!/bin/bash\nsrc=$1\ndest="$2/backup-$(date +%Y%m%d)"\nmkdir -p "$dest"\n'
                         'for f in "$src"/*.txt; do\n    [ -e "$f" ] || continue\n    cp "$f" "$dest/"\n'
                         '    echo "backed up $(basename "$f")"\ndone\necho "done: $(ls "$dest" | wc -l) files"\n')
    return "Fixed"

def rename_symbol(d):
    for p in d.rglob("*"):
        if p.is_file() and p.suffix in (".py", ".md"):
            p.write_text(re.sub(r"\bget_usr\b", "get_user", p.read_text()))
    return "Renamed"

def config_trace(d):
    return "Port 7000: `listen` in config/base.toml wins over port 8443 in config/production.toml."

def crash_from_log(d):
    p = d / "config.json"
    p.write_text(p.read_text().replace('"retires"', '"retries"'))
    return "A typo in config.json: retires for retries."

def sqlite_query(d):
    text(d, "top_customers.sql", "SELECT c.name, ROUND(SUM(i.quantity * i.unit_price), 2) AS total FROM customers c "
         "JOIN orders o ON o.customer_id = c.id JOIN order_items i ON i.order_id = o.id "
         "WHERE strftime('%Y', o.ordered_at) = '2025' GROUP BY c.id ORDER BY total DESC LIMIT 5;\n")
    return "Written"

def multi_bug(d):
    fixes = {"inventory/money.py": ('    return f"£{amount:,}"',
                                    '    sign = "-" if amount < 0 else ""\n    return f"{sign}£{abs(amount):,}"'),
             "inventory/csvio.py": ("csv.DictReader(rows)", "csv.DictReader(rows, skipinitialspace=True)"),
             "inventory/pricing.py": ("if qty > minimum:", "if qty >= minimum:"),
             "inventory/stock.py": ("key=lambda i: i.qty)", "key=lambda i: (i.qty, i.sku))")}
    for name, (old, new) in fixes.items():
        p = d / name
        assert old in p.read_text(), (name, old)
        p.write_text(p.read_text().replace(old, new))
    return "Fixed 4 bugs"

MIGRATED = {
    "orders.py": 'import notify\n\n\ndef order_shipped(order_id, user_id):\n'
                 '    notify.Client().send(user_id, f"Order {order_id} has shipped")\n',
    "billing.py": 'import notify\n\nBILLING = notify.Client("billing")\n\n\ndef payment_failed(user):\n'
                  '    BILLING.send(user["id"], "Your payment failed. Please update your card.", '
                  'priority=notify.Priority.HIGH)\n\n\ndef invoice_ready(uid, invoice_no):\n'
                  '    BILLING.send(uid, f"Invoice {invoice_no} is ready")\n',
    "alerts.py": 'import notify\n\n\ndef alert(uid, message, is_urgent):\n    notify.Client().send(uid, message, '
                 'priority=notify.Priority.HIGH if is_urgent else notify.Priority.NORMAL)\n',
    "signup.py": 'import notify\n\n\ndef welcome(user_id, name):\n'
                 '    notify.Client().send(user_id, f"Welcome, {name}!")\n',
    "reminders.py": 'import notify\n\n\ndef renewal_reminders(subscriptions):\n    client = notify.Client("renewals")\n'
                    '    for sub in subscriptions:\n        days = sub["days_left"]\n'
                    '        client.send(sub["user_id"], f"Your plan renews in {days} days", '
                    'priority=notify.Priority.HIGH if days < 2 else notify.Priority.NORMAL)\n',
    "support.py": 'import notify\n\n\ndef ticket_answered(user_id, ticket):\n'
                  '    notify.Client("support").send(user_id, f"Ticket #{ticket} has a reply")\n',
    "security.py": 'import notify\n\nSECURITY = "security"\n\n\ndef new_login(user_id, device):\n'
                   '    notify.Client(SECURITY).send(user_id, f"New sign-in from {device}", '
                   'priority=notify.Priority.HIGH)\n\n\ndef password_changed(user_id):\n'
                   '    notify.Client(SECURITY).send(user_id, "Your password was changed", '
                   'priority=notify.Priority.HIGH)\n',
    "digest.py": 'import notify\n\n\ndef weekly_digest(user_ids, items):\n    text = "This week: " + ", ".join(items)\n'
                 '    for uid in user_ids:\n        notify.Client().send(uid, text)\n',
}

def api_migration(d):
    for name, code in MIGRATED.items():
        text(d, f"app/{name}", code)
    return "Migrated"

# ----- xl tasks: their references reuse the checkers' own answers, so they check the setup and the checkers' parsing
def xl_lang_bugs(d):
    from xl_lang_bugs import BUGS
    for name, good, bad in BUGS:
        text(d, name, (d / name).read_text().replace(bad, good))
    return "Fixed"

FEATURE_PATCHES = [
    ("minilang/lexer.py", '"and", "or", "not"}', '"and", "or", "not", "for", "in", "break",\n            "continue"}'),
    ("minilang/ast.py", "@dataclass\nclass Return:",
     "@dataclass\nclass For:\n    name: str\n    iterable: object\n    body: Block\n\n\n@dataclass\nclass Break:\n"
     "    line: int = 0\n\n\n@dataclass\nclass Continue:\n    line: int = 0\n\n\n@dataclass\nclass Return:"),
    ("minilang/parser.py", "Num, Program, Return, Str, Unary, While)",
     "Num, Program, Return, Str, Unary, While, For, Break, Continue)"),
    ("minilang/parser.py", "        self.tokens, self.pos = tokens, 0\n",
     "        self.tokens, self.pos = tokens, 0\n        self.loops = 0\n"),
    ("minilang/parser.py", "            cond = self.expression()\n            return While(cond, self.block())\n",
     "            cond = self.expression()\n            return While(cond, self.loop_body())\n"
     "        if self.at(\"kw\", \"for\"):\n            self.next()\n            name = self.expect(\"name\").value\n"
     "            self.expect(\"kw\", \"in\")\n            iterable = self.expression()\n"
     "            return For(name, iterable, self.loop_body())\n"
     "        if self.at(\"kw\", \"break\") or self.at(\"kw\", \"continue\"):\n            token = self.next()\n"
     "            if not self.loops:\n"
     "                raise ParseError(f\"{token.value} outside a loop\", token.line)\n"
     "            self.expect(\"op\", \";\")\n"
     "            return (Break if token.value == \"break\" else Continue)(token.line)\n"),
    ("minilang/parser.py", "    def if_statement(self):",
     "    def loop_body(self):\n        self.loops += 1\n        try:\n            return self.block()\n"
     "        finally:\n            self.loops -= 1\n\n    def if_statement(self):"),
    ("minilang/parser.py", "        self.expect(\"op\", \")\")\n        return params, self.block()\n",
     "        self.expect(\"op\", \")\")\n        outer, self.loops = self.loops, 0\n        try:\n"
     "            return params, self.block()\n        finally:\n            self.loops = outer\n"),
    ("minilang/interpreter.py", "class Interpreter:",
     "class BreakSignal(Exception):\n    pass\n\n\nclass ContinueSignal(Exception):\n    pass\n\n\nclass Interpreter:"),
    ("minilang/interpreter.py",
     "        while truthy(self.eval(node.cond, env)):\n            self.exec_Block(node.body, env)\n",
     "        while truthy(self.eval(node.cond, env)):\n            try:\n                self.exec_Block(node.body, env)\n"
     "            except BreakSignal:\n                break\n            except ContinueSignal:\n                continue\n\n"
     "    def exec_For(self, node, env):\n        items = self.eval(node.iterable, env)\n"
     "        if not isinstance(items, (list, str)):\n"
     "            raise EvalError(f\"can't loop over a {type_name(items)}\")\n        i = 0\n"
     "        while i < len(items):\n            scope = Environment(env)\n            scope.define(node.name, items[i])\n"
     "            i += 1\n            try:\n                for stmt in node.body.stmts:\n"
     "                    self.execute(stmt, scope)\n            except BreakSignal:\n                break\n"
     "            except ContinueSignal:\n                continue\n\n"
     "    def exec_Break(self, node, env):\n        raise BreakSignal()\n\n"
     "    def exec_Continue(self, node, env):\n        raise ContinueSignal()\n"),
    ("minilang/formatter.py", "    if isinstance(node, ast.If):\n",
     "    if isinstance(node, ast.For):\n"
     "        return f\"{pad}for {node.name} in {expr(node.iterable, depth)} {block(node.body, depth)}\\n\"\n"
     "    if isinstance(node, ast.Break):\n        return f\"{pad}break;\\n\"\n"
     "    if isinstance(node, ast.Continue):\n        return f\"{pad}continue;\\n\"\n"
     "    if isinstance(node, ast.If):\n"),
]
FEATURE_TEST = '''import unittest

from minilang.errors import ParseError
from tests.helpers import output


class TestFor(unittest.TestCase):
    def test_for_break_continue(self):
        self.assertEqual(output("for x in range(6) { if x == 1 { continue; } if x == 4 { break; } print(x); }"),
                         ["0", "2", "3"])

    def test_outside(self):
        with self.assertRaises(ParseError):
            output("break;")
'''

def xl_lang_feature(d):
    for name, old, new in FEATURE_PATCHES:
        text(d, name, (d / name).read_text().replace(old, new))
    text(d, "tests/test_for.py", FEATURE_TEST)
    return "Implemented"

def xl_meeting_actions(d):
    from xl_meeting_actions import ITEMS, expected
    rows = [f"{ITEMS[k][2]},{owner},{due},{status}" for k, (owner, due, status) in expected().items()]
    text(d, "actions.csv", "item,owner,due,status\n" + "\n".join(rows) + "\n")
    return "Written"

def xl_contracts(d):
    from xl_contracts import CONTRACTS, expected
    names = {c["key"]: c["name"] for c in CONTRACTS}
    rows = [f'"{names[k]}",{due},{fee}' for k, (due, fee) in expected().items()]
    text(d, "notice.csv", "supplier,deadline,annual_fee\n" + "\n".join(rows) + "\n")
    return "Written"

def xl_expense_audit(d):
    from xl_expense_audit import expected
    want, _ = expected()
    text(d, "violations.csv", "claim_id,reason\n" + "".join(f"{k},{'; '.join(v)}\n" for k, v in want.items()))
    return "Written"

def slow_reports(d):  # the reports as the script would write them, without its wait
    from slow_reports import REGIONS, data
    totals = {}
    for g in REGIONS:
        rows = [(p, c) for a, p, c in data() if a == g]
        by = {}
        for p, c in rows:
            by[p] = by.get(p, 0) + c
        totals[g] = sum(by.values())
        text(d, f"reports/{g}.csv", "product,amount\n" + "".join(f"{p},{c:.2f}\n" for p, c in sorted(by.items()))
             + f"TOTAL,{totals[g]:.2f}\n")
    best = max(totals, key=totals.get)
    return f"{best.capitalize()} had the highest total, {totals[best]:,.2f}."

ANSWERS = {"slow_tests": "Two fail: tests_api test_pagination_cursor (20 != 25) and tests_ui test_dark_mode_toggle.",
           "web_wiki_fact": "It was completed in March 1889.", "web_pypi_license": "Apache-2.0",
           "web_stackoverflow": "git reset --soft HEAD~1"}


def main():
    tasks = load_tasks(sys.argv[1:] or ["*"], web=True)
    failed = 0
    for name, task in tasks.items():
        d = Path(tempfile.mkdtemp(prefix=f"selftest-{name}-"))
        task.setup(d)
        before, why_before = (task.check(d, "") if not task.WEB else (False, "web: not checked offline"))
        solve = globals().get(name)
        answer = solve(d) if solve else ANSWERS[name]
        after, why_after = task.check(d, answer)
        good = not before and after
        failed += not good
        print(f"{'ok  ' if good else 'FAIL'} {name:<18} nothing done: {'passes!' if before else 'fails'}; "
              f"reference: {'passes' if after else 'fails: ' + why_after}")
        shutil.rmtree(d, ignore_errors=True)
    print(f"\n{len(tasks) - failed} of {len(tasks)} tasks ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
