import csv, re
from datetime import date, timedelta
from pathlib import Path
from _lib import write, rng

PROMPT = ("Combine my statements (bank_a.csv, bank_b.csv and card_c.txt) and write summary.csv with the columns "
          "month,category,total: my total spending for each month (as YYYY-MM) and category, using the keywords in "
          "categories.txt, with spending that matches no keyword as Other. Totals are positive, with two decimals. "
          "Count spending only: leave out income, and transfers between my own accounts (they say TRANSFER).")
KIND, SIZE, WEB = "everyday", "long", False

MERCHANTS = {"TESCO STORES 2231": "Groceries", "ALDI 118": "Groceries", "SHELL FUEL A40": "Transport",
             "UBER *TRIP": "Transport", "NETFLIX.COM": "Subscriptions", "SPOTIFY P1": "Subscriptions",
             "CAFE NERO": "Eating out", "PRET A MANGER": "Eating out", "BOOTS PHARMACY": "Health",
             "HARDWARE PLUS": None, "MARKET STALL 12": None, "CITY PARKING": None}
CATEGORIES = """# keyword = category (a keyword matches anywhere in the description, in any case)
tesco = Groceries
aldi = Groceries
shell = Transport
uber = Transport
netflix = Subscriptions
spotify = Subscriptions
nero = Eating out
pret = Eating out
boots = Health
"""

def transactions():  # -> [(account, date, description, amount)], spending negative
    r, out = rng(3), []
    for account in ("a", "b", "c"):
        day = date(2025, 10, 1)
        while day < date(2025, 12, 1):
            for _ in range(r.choice((0, 1, 1, 2))):
                merchant = r.choice(list(MERCHANTS))
                out.append((account, day, merchant, -round(r.uniform(2, 120), 2)))
            day += timedelta(days=1)
        if account != "c":
            out.append((account, date(2025, 10, 28), "SALARY ACME LTD", 2450.00))
            out.append((account, date(2025, 11, 28), "SALARY ACME LTD", 2450.00))
        out.append((account, date(2025, 11, 3), f"TRANSFER TO SAVINGS {account.upper()}", -300.00))
    out.append(("a", date(2025, 10, 15), "CARD C PAYMENT TRANSFER", -250.00))
    out.append(("c", date(2025, 10, 16), "PAYMENT RECEIVED TRANSFER THANK YOU", 250.00))
    return out

def setup(d):
    rows = transactions()
    a = ["Date,Description,Amount"] + [f"{t:%d/%m/%Y},{desc},{amt:.2f}" for acc, t, desc, amt in rows if acc == "a"]
    write(d, "bank_a.csv", "\n".join(a) + "\n")
    b = ["date;payee;debit;credit"]
    for acc, t, desc, amt in rows:
        if acc == "b":
            money = f"{abs(amt):.2f}".replace(".", ",")
            b.append(f'{t:%Y-%m-%d};"{desc}";{money if amt < 0 else ""};{money if amt > 0 else ""}')
    write(d, "bank_b.csv", "\n".join(b) + "\n")
    c = ["CARD STATEMENT  **** 4421", "", f"{'DATE':<12}{'MERCHANT':<40}{'AMOUNT':>10}"]
    c += [f"{t.strftime('%d %b %y').upper():<12}{desc:<40}{-amt:>10.2f}" for acc, t, desc, amt in rows if acc == "c"]
    write(d, "card_c.txt", "\n".join(c) + "\n\nAmounts are charges; negative amounts are payments to the card.\n")
    write(d, "categories.txt", CATEGORIES)

def expected():
    totals = {}
    for _, t, desc, amt in transactions():
        if amt >= 0 or "TRANSFER" in desc:
            continue
        category = MERCHANTS[desc] or "Other"
        key = (f"{t:%Y-%m}", category)
        totals[key] = round(totals.get(key, 0) - amt, 2)
    return totals

def check(d, answer):
    path = Path(d, "summary.csv")
    if not path.is_file():
        return False, "no summary.csv"
    rows = list(csv.reader(path.read_text(errors="replace").splitlines()))
    if not rows or [c.strip().lower() for c in rows[0]] != ["month", "category", "total"]:
        return False, f"header is {rows[:1]}"
    got = {}
    for row in rows[1:]:
        if not row or not any(row):
            continue
        try:
            got[(row[0].strip(), row[1].strip())] = abs(float(re.sub(r"[^\d.\-]", "", row[2])))
        except (ValueError, IndexError):
            return False, f"bad row {row}"
    want = expected()
    for key, total in want.items():
        if key not in got or abs(got[key] - total) > 0.011:
            return False, f"{key}: expected {total:.2f}, got {got.get(key)}"
    extra = [k for k, v in got.items() if k not in want and v]
    return not extra, f"extra rows {extra}" if extra else "all totals right"
