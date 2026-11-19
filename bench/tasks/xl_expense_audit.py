import csv, io, re
from datetime import date, timedelta
from pathlib import Path
from _lib import write, rng

PROMPT = ("Audit our expense claims for January to June 2026 against policy.md. The claims are in claims/ (one file "
          "per month of submission), with employees.csv and rates.csv alongside. Write violations.csv with the "
          "columns claim_id,reason: one row for every claim that breaks the policy in any way, and no others.")
KIND, SIZE, WEB = "everyday", "xl", False

APRIL = date(2026, 4, 1)  # the policy's changes from version 3
ALCOHOL = ("wine", "beer", "prosecco", "cocktail", "bar tab", "champagne")
CITIES = {"London": "GBP", "Manchester": "GBP", "Leeds": "GBP", "Bristol": "GBP", "Paris": "EUR", "Berlin": "EUR",
          "New York": "USD", "Chicago": "USD"}
MONTHS = [f"{y}-{m:02d}" for y, m in [(2025, 10), (2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 7)]]

POLICY = """# Expenses policy

Version 3. Owner: Finance. Applies to all employees of Kestrel Home Goods Ltd.

## 1. Purpose

This policy explains which business expenses the company pays back, and how to claim them. It aims to be fair to
employees, who should never be out of pocket for doing their job, and to the company, which has to account for every
pound it spends. If you are unsure whether something can be claimed, ask Finance before you spend the money rather
than after. Managers who approve claims are expected to know this policy and to apply it consistently.

The policy covers travel, accommodation, meals, equipment and sundry items bought for work. It does not cover items
bought on a company card, which follow the card policy, or relocation costs, which are agreed case by case with HR.

## 2. General principles

Spend the company's money as if it were your own. Choose the cheapest option that is reasonable for the purpose:
standard class rail travel, economy flights for journeys under six hours, and hotels of a mid-range standard. Where
you can, book through the company's travel portal, which has negotiated rates with many hotels and the main rail
operators.

Claims are made through the expenses system, one claim per receipt. Each claim records the date the expense was
incurred, the date it was submitted, the category, the amount and currency as paid, whether a receipt is attached,
how many people the expense covered (yourself included), and a description. The description should say what the
expense was for, and include the details this policy asks for in each category.

## 3. Receipts

Every claim of £25.00 or more must have a receipt attached. Claims under £25.00 do not need one, although we
encourage you to keep them. Mileage claims never need a receipt, since there is nothing to receipt: the description
of the journey takes its place. If you lose a receipt for a claim that needs one, the claim cannot be paid; talk to
Finance, who may be able to find another way to help.

Where an amount was paid in a foreign currency, all the limits in this policy, including this one, apply to the amount
in pounds, converted as described in section 10.

## 4. Deadlines

Claims must be submitted within 60 days of the date of the expense. A claim submitted more than 60 days after the
expense was incurred breaks this policy and will not be paid, whatever the reason for the delay. Managers should
approve or query claims within ten working days of their submission.

## 5. Travel

### Rail and air

Book rail travel in standard class, and as early as you can: advance tickets are often far cheaper. First class may be
booked only when it is cheaper than standard class on the day, which happens more often than you might think on some
routes. Flights should be economy class for journeys under six hours. Taxis are allowed when public transport is not
practical, for example late at night, when carrying heavy equipment, or when several colleagues share one.

### Mileage

If you use your own car for business travel you can claim a mileage allowance for the business miles you drive. The
allowance covers fuel, wear and tear and insurance, so none of these can be claimed separately. Put the number of
miles in the description, written as a number followed by "miles", for example "Leeds to York and back, 52 miles".

The allowance is 45p per mile. The amount claimed must not be more than the miles multiplied by the rate, rounded to
the nearest penny; claiming less is fine. Commuting between your home and your usual office is not business travel.

## 6. Accommodation

Stay in a mid-range hotel close to where you are working. The cost per night, including breakfast and taxes, must not
be more than £160 in London and £120 anywhere else. A hotel claim covers a whole stay: put the number of nights in the
description, for example "Hotel Ibis, 2 nights, client workshop". The limit applies to the amount claimed divided by
the number of nights. The date of a hotel claim is the date of arrival.

If no room within the limit is available, book the cheapest room you can find and ask Finance to approve the
difference in advance; approved exceptions are made outside the expenses system, so they never appear as claims.

## 7. Meals

### Meals when travelling

When you are away from your usual office for work, you can claim for meals. Each meal claim may cost up to £30.00
per person. Managers and directors may claim up to £45.00 per person, because they more often have to eat at short
notice in expensive places.

### Client entertainment

When you take clients or partners out for a meal, the limit is £60.00 per person, counting everyone at the table,
yourself included. Record the number of people in the claim. Any meal claim covering more than one person is treated
as client entertainment, whoever claims it.

### Alcohol

The company does not pay for alcohol, and claims that include it break this policy, with one exception: alcohol served
as part of client entertainment (a meal claim covering more than one person) is allowed, within the per-person limit.
Describe meals accurately, including any drinks.

## 8. Equipment and supplies

Small items needed for work, such as stationery, cables or a replacement charger, can be bought and claimed. Any
equipment or supply claim of more than £100.00 needs a purchase order raised in advance, and its number must be in the
description, in the form PO-1234. Without one, the claim breaks this policy. Items bought for work belong to the company
and must be returned when you leave.

## 9. Weekends

Expenses incurred on a Saturday or a Sunday need your manager's approval in advance, because weekend work is the
exception. Record it in the description as "approved by" and your manager's name, for example "approved by K. Moss".
Hotel claims are exempt from this rule, since many trips start on a Sunday evening.

## 10. Foreign currency

Claim foreign currency expenses in the currency you paid in. Finance converts them to pounds using the rate for the
month in which the expense was incurred, as published in the company's rates table (rates.csv), and rounds the result
to the nearest penny. All limits in this policy apply to the converted amount.

## 11. Duplicate claims

Each expense can be claimed only once. If the same employee claims the same amount, in the same currency and category,
for the same date more than once, only the first claim (the one with the lowest claim number) is paid; every later
copy breaks this policy.

## 12. Senior staff

Directors travel often and at short notice. Their hotel limit is £200 per night, in London and everywhere else. In all
other respects directors follow this policy like everyone else.

## 13. Breaches

A claim that breaks this policy is rejected in full, not reduced to the limit. Repeated breaches may lead to
disciplinary action. Managers who approve claims that break this policy may be asked to explain why.

## 14. Changes in this version

Version 3 makes two changes, both for expenses incurred on or after 1 April 2026 (earlier expenses follow the old
rules, whenever they are submitted):

- the mileage allowance falls from 45p to 40p per mile, in line with the lower cost of fuel;
- the meal limit for employees who aren't managers or directors rises from £30.00 to £35.00 per person.

Everything else is unchanged from version 2.
"""


def gbp(c, rates):
    rate = 1.0 if c["currency"] == "GBP" else rates[(c["date"][:7], c["currency"])]
    return round(float(c["amount"]) * rate + 1e-9, 2)


def rules(c, employees, rates, seen):  # -> the reasons a claim breaks the policy
    why = []
    amount, grade = gbp(c, rates), employees[c["employee_id"]]
    day, desc, cat = date.fromisoformat(c["date"]), c["description"].lower(), c["category"]
    people = int(c["people"])
    if cat != "mileage" and amount >= 25 and c["receipt"] != "yes":
        why.append("no receipt")
    if (date.fromisoformat(c["submitted"]) - day).days > 60:
        why.append("late")
    if cat == "meal":
        if people > 1:
            limit = 60
        elif grade in ("manager", "director"):
            limit = 45
        else:
            limit = 35 if day >= APRIL else 30
        if amount / people > limit:
            why.append("meal over limit")
        if people == 1 and any(w in desc for w in ALCOHOL):
            why.append("alcohol")
    if cat == "hotel":
        nights = int(re.search(r"(\d+) nights?", desc)[1])
        limit = 200 if grade == "director" else 160 if c["city"] == "London" else 120
        if amount / nights > limit:
            why.append("hotel over limit")
    if cat == "mileage":
        miles = int(re.search(r"(\d+) miles", desc)[1])
        if amount > round(miles * (0.40 if day >= APRIL else 0.45), 2):
            why.append("mileage over rate")
    if cat in ("equipment", "supplies") and amount > 100 and not re.search(r"\bPO-\d{4}\b", c["description"]):
        why.append("no purchase order")
    if day.weekday() >= 5 and cat != "hotel" and "approved by" not in desc:
        why.append("weekend without approval")
    key = (c["employee_id"], c["date"], c["category"], c["amount"], c["currency"])
    if key in seen:
        why.append("duplicate")
    seen.add(key)
    return why


FIRST_NAMES = ["Amy", "Ben", "Chloe", "Dev", "Ella", "Femi", "Gus", "Hana", "Ivan", "Jade", "Kai", "Lola", "Max",
               "Nina", "Owen", "Pia", "Raj", "Sara", "Theo", "Uma", "Vic", "Will", "Xia", "Yusuf", "Zoe", "Arlo",
               "Bea", "Cal", "Dina", "Eli", "Fay", "Gil", "Ines", "Jon", "Kim", "Leo"]
MEALS = ["Lunch", "Dinner", "Breakfast", "Sandwich and coffee", "Evening meal"]
PLACES = ["at the station", "near the client's office", "at the hotel", "at a café", "on the train", "at Wagamama",
          "at Pizza Express", "at the conference venue"]
TRIPS = [("Leeds to York and back", 52), ("Manchester to Liverpool and back", 70), ("Leeds to Sheffield and back", 76),
         ("Bristol to Cardiff and back", 92), ("Leeds to Hull and back", 120), ("Manchester to Chester and back", 84),
         ("Leeds to Newcastle and back", 196), ("London to Reading and back", 82), ("Bristol to Bath and back", 26),
         ("Leeds to Harrogate and back", 32)]
ITEMS = [("USB-C charger", 25, 40), ("Notebooks and pens", 8, 30), ("HDMI cable", 9, 20), ("Monitor", 140, 260),
         ("Office chair", 150, 320), ("Headset", 45, 95), ("Printer toner", 60, 140), ("Keyboard and mouse", 30, 90),
         ("Portable projector", 180, 400), ("Display boards for trade stand", 90, 99)]


def generate():  # -> (employees {id: grade}, rates {(month, cur): rate}, rows), all from a fixed seed
    r = rng(4103)
    employees = {}
    for i, name in enumerate(FIRST_NAMES, 1):
        grade = "director" if i % 12 == 0 else "manager" if i % 4 == 0 else "staff"
        employees[f"E{i:03d}"] = (name + " " + r.choice(["Smith", "Khan", "Jones", "Novak", "Okoro", "Lee", "Brown",
                                                           "Garcia", "Walsh", "Chen"]), grade)
    rates = {}
    for m in MONTHS:
        rates[(m, "EUR")] = round(r.uniform(0.84, 0.88), 4)
        rates[(m, "USD")] = round(r.uniform(0.76, 0.81), 4)
    grades = {k: g for k, (_, g) in employees.items()}
    rows, n = [], 0
    start = date(2025, 11, 20)
    for k in range(900):
        day = start + timedelta(days=r.randint(0, 210))
        while day.weekday() >= 5 and r.random() < 0.8:
            day -= timedelta(days=1)
        emp = r.choice(list(employees))
        grade = grades[emp]
        city = r.choice(list(CITIES))
        cur = CITIES[city]
        bad = r.random() < 0.18  # aim for a breach (of the kind below); otherwise stay clear of every limit
        cat = r.choices(["meal", "hotel", "mileage", "taxi", "train", "equipment", "supplies"],
                        [32, 12, 14, 10, 14, 8, 10])[0]
        people, desc, receipt = 1, "", "yes"
        rate = 1.0 if cur == "GBP" else rates[(f"{day:%Y-%m}", cur)]
        to_local = lambda pounds: round(pounds / rate, 2)
        if cat == "meal":
            people = 1 if r.random() < 0.7 else r.randint(2, 6)
            limit = 60 if people > 1 else 45 if grade in ("manager", "director") else (35 if day >= APRIL else 30)
            if bad and r.random() < 0.5:
                per = limit * r.uniform(1.05, 1.4)
            elif people == 1 and grade == "staff" and day < APRIL and r.random() < 0.3:
                per = r.uniform(31, 34)  # fine from April, not before: the change in version 3
                if day < APRIL:
                    bad = True
            else:
                per = limit * r.uniform(0.3, 0.95)
            pounds = per * people
            drink = ""
            if (bad and r.random() < 0.4) or (people > 1 and r.random() < 0.5):
                drink = f", incl. {r.choice(['a glass of wine', 'two beers', 'prosecco', 'cocktails', 'a bottle of wine'])}"
            what = r.choice(MEALS) if people == 1 else f"Client dinner, {people} people"
            desc = f"{what} {r.choice(PLACES)}{drink}"
        elif cat == "hotel":
            nights = r.randint(1, 4)
            limit = 200 if grade == "director" else 160 if city == "London" else 120
            if bad and r.random() < 0.5:
                per = limit * r.uniform(1.04, 1.3)
            elif grade == "director" and r.random() < 0.5:
                per = r.uniform(165, 195)  # over the usual limit, within a director's
            else:
                per = limit * r.uniform(0.6, 0.96)
            pounds = per * nights
            desc = f"Hotel {r.choice(['Ibis', 'Premier Inn', 'Novotel', 'Holiday Inn', 'Mercure'])}, " \
                   f"{nights} night{'s' * (nights > 1)}, {r.choice(['client visit', 'trade show', 'training', 'site audit'])}"
            if city not in ("London",) and CITIES[city] == "GBP":
                desc += f", {city}"
        elif cat == "mileage":
            trip, miles = r.choice(TRIPS)
            city, cur, rate = "Leeds", "GBP", 1.0
            to_local = lambda pounds: round(pounds, 2)
            mrate = 0.40 if day >= APRIL else 0.45
            if bad and r.random() < 0.6:
                pounds = miles * mrate + r.choice([0.5, 1.0, 2.6, miles * 0.05])
            elif day >= APRIL and r.random() < 0.4:
                pounds = miles * 0.45  # the old rate, after it changed
            else:
                pounds = miles * mrate * r.choice([1, 1, 1, 0.9])
            desc = f"{trip}, {miles} miles"
        elif cat in ("taxi", "train"):
            pounds = r.uniform(6, 24) if cat == "taxi" else r.uniform(12, 140)
            desc = (f"Taxi {r.choice(['from the station to the client', 'back to the hotel', 'to the airport'])}"
                    if cat == "taxi" else f"Train ticket, {r.choice(['standard advance', 'off-peak return', 'anytime single'])}")
        else:
            name, low, high = r.choice(ITEMS)
            pounds = r.uniform(low, high)
            cat = "equipment" if high > 100 else "supplies"
            desc = name
            if pounds > 100 and not (bad and r.random() < 0.6):
                desc += f", PO-{r.randint(1000, 9999)}"
            elif pounds > 100 and r.random() < 0.3:
                desc += ", PO pending"
        amount = to_local(pounds)
        if cat != "mileage" and bad and r.random() < 0.3:
            receipt = "no"
        elif cat == "mileage" or (amount * rate < 25 and r.random() < 0.6):
            receipt = "no"
        if day.weekday() >= 5 and cat != "hotel" and not (bad and r.random() < 0.7):
            desc += f", approved by {r.choice(['K. Moss', 'R. Iqbal', 'T. Fox'])}"
        delay = r.randint(1, 30) if not (bad and r.random() < 0.25) else r.randint(55, 75)
        submitted = day + timedelta(days=delay)
        if not date(2026, 1, 1) <= submitted <= date(2026, 6, 30):
            continue
        n += 1
        rows.append({"claim_id": f"X{n:04d}", "employee_id": emp, "date": day.isoformat(),
                     "submitted": submitted.isoformat(), "category": cat, "amount": f"{amount:.2f}",
                     "currency": cur, "receipt": receipt, "people": str(people), "city": city, "description": desc})
        if r.random() < 0.025:  # the same claim again, later
            n += 1
            again = dict(rows[-1], claim_id=f"X{n:04d}", submitted=(submitted + timedelta(days=r.randint(0, 20))).isoformat())
            if again["submitted"] <= "2026-06-30":
                rows.append(again)
    return employees, rates, rows


def expected():
    employees, rates, rows = generate()
    grades = {k: g for k, (_, g) in employees.items()}
    seen = set()
    return {c["claim_id"]: why for c in sorted(rows, key=lambda c: c["claim_id"])
            if (why := rules(c, grades, rates, seen))}, rows


def setup(d):
    employees, rates, rows = generate()
    write(d, "policy.md", POLICY)
    write(d, "employees.csv", "employee_id,name,grade\n" + "".join(f"{k},{n},{g}\n" for k, (n, g) in employees.items()))
    write(d, "rates.csv", "month,currency,gbp_per_unit\n" + "".join(f"{m},{c},{v}\n" for (m, c), v in rates.items()))
    fields = list(rows[0])
    for month in sorted({c["submitted"][:7] for c in rows}):
        out = io.StringIO()
        w = csv.DictWriter(out, fields, lineterminator="\n")
        w.writeheader()
        w.writerows(c for c in rows if c["submitted"][:7] == month)
        write(d, f"claims/{month}.csv", out.getvalue())


def check(d, answer):
    path = Path(d, "violations.csv")
    if not path.exists():
        return False, "no violations.csv"
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    header = [h.strip().lower() for h in rows[0]] if rows else []
    if "claim_id" not in header:
        return False, f"columns are {rows[0] if rows else 'missing'}"
    got = {row[header.index("claim_id")].strip() for row in rows[1:] if row and row[header.index("claim_id")].strip()}
    want, _ = expected()
    missing, extra = sorted(set(want) - got), sorted(got - set(want))
    detail = (f"{len(want)} expected; missing {len(missing)}: "
              + ", ".join(f"{m} ({'/'.join(want[m])})" for m in missing[:8])
              + f"; extra {len(extra)}: " + ", ".join(extra[:8]))
    return not missing and not extra, detail
