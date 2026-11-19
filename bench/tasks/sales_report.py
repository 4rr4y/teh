from datetime import date, timedelta
from _lib import write, has_number, rng

PROMPT = ("sales.csv has last year's sales. Which region had the highest revenue (units times unit price) in Q3, July "
          "to September? Give the region and its Q3 revenue, rounded to whole dollars.")
KIND, SIZE, WEB = "everyday", "short", False

PRODUCTS = {"Kettle": 39.90, "Toaster": 54.50, "Blender": 89.00, "Mug set": 18.25, "Teapot": 32.75, "Scale": 24.99}
REGIONS = ("North", "South", "East", "West", "Central")

def rows():
    r, day, out = rng(11), date(2025, 1, 1), []
    while day.year == 2025:
        for _ in range(8):
            region, product = r.choice(REGIONS), r.choice(list(PRODUCTS))
            price = PRODUCTS[product] if r.random() > 0.15 else round(PRODUCTS[product] * 0.8, 2)  # some on sale
            units = r.randint(1, 20) + (6 if region == "East" and day.month in (8, 9) else 0)
            out.append((day.isoformat(), region, product, units, price))
        day += timedelta(days=1)
    return out

def setup(d):
    write(d, "sales.csv", "date,region,product,units,unit_price\n"
          + "".join(f"{a},{b},{c},{u},{p:.2f}\n" for a, b, c, u, p in rows()))

def check(d, answer):
    totals = {}
    for day, region, _, units, price in rows():
        if "2025-07-01" <= day <= "2025-09-30":
            totals[region] = totals.get(region, 0) + units * price
    best = max(totals, key=totals.get)
    ok = best.lower() in answer.lower() and has_number(answer, round(totals[best]), 1)
    return ok, f"expected {best} with {totals[best]:,.2f}"
