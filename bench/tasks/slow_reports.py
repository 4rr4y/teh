import csv, re
from pathlib import Path
from _lib import write, rng

PROMPT = ("Generate the sales reports for the north, south and west regions with `python3 make_report.py REGION` "
          "(each takes about half a minute), then tell me which region had the highest total.")
KIND, SIZE, WEB = "everyday", "slow", False

SCRIPT = '''"""Builds reports/REGION.csv from sales.csv: the region's sales by product, and a total. It's slow: it waits
for the (pretend) warehouse system to confirm each figure."""
import csv, sys, time
from collections import Counter
from pathlib import Path

region = sys.argv[1] if len(sys.argv) == 2 else sys.exit("usage: python3 make_report.py REGION")
rows = [r for r in csv.DictReader(open("sales.csv")) if r["region"] == region]
if not rows:
    sys.exit(f"no sales for region {region!r}")
totals = Counter()
for r in rows:
    totals[r["product"]] += float(r["amount"])
time.sleep(28)
Path("reports").mkdir(exist_ok=True)
with open(f"reports/{region}.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["product", "amount"])
    for product, amount in sorted(totals.items()):
        w.writerow([product, f"{amount:.2f}"])
    w.writerow(["TOTAL", f"{sum(totals.values()):.2f}"])
print(f"wrote reports/{region}.csv")
'''
REGIONS = ("north", "south", "west")

def data():
    r = rng(4201)
    rows = [(region, r.choice(["kettles", "mugs", "teapots", "strainers"]), round(r.uniform(5, 120), 2))
            for region in REGIONS for _ in range(r.randint(60, 90))]
    rows += [("east", "mugs", 9999.0)]  # a region nobody asked about, with the biggest total of all
    return rows

def setup(d):
    write(d, "make_report.py", SCRIPT)
    write(d, "sales.csv", "region,product,amount\n" + "".join(f"{a},{b},{c}\n" for a, b, c in data()))

def check(d, answer):
    totals = {g: sum(c for a, _, c in data() if a == g) for g in REGIONS}
    best = max(totals, key=totals.get)
    missing = [g for g in REGIONS if not Path(d, "reports", f"{g}.csv").exists()]
    if missing:
        return False, f"reports missing: {missing}"
    for g in REGIONS:
        last = list(csv.reader(open(Path(d, "reports", f"{g}.csv"))))[-1]
        if last[0] != "TOTAL" or abs(float(last[1]) - totals[g]) > 0.01:
            return False, f"reports/{g}.csv was changed or is wrong"
    # what the answer calls the highest: the region on a line saying "highest" (or "most", "top", "largest"), else
    # the first region it names
    lines = [line for line in answer.splitlines() if re.search(r"highest|most|top|largest|biggest", line, re.I)]
    def named(text):  # the regions in text, in the order they appear
        found = [(m.start(), g) for g in REGIONS + ("east",) for m in [re.search(rf"\b{g}\b", text, re.I)] if m]
        return [g for _, g in sorted(found)]
    claimed = next((named(line) for line in lines if named(line)), None) or named(answer)[:1]
    return claimed[:1] == [best], f"best is {best} ({totals[best]:.2f}); the answer calls {claimed[:1]} the highest"
