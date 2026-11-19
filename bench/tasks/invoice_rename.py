import re
from datetime import date
from pathlib import Path
from _lib import write, has_number, rng

PROMPT = ("Rename each invoice in invoices/ to DATE_VENDOR.txt, where DATE is the invoice date as YYYY-MM-DD and "
          "VENDOR the vendor's name in lower case with hyphens for spaces (e.g. 2025-10-03_harbour-coffee.txt). Then "
          "write invoices/total.txt with the sum of all the invoices' totals.")
KIND, SIZE, WEB = "everyday", "short", False

VENDORS = ("Harbour Coffee", "Blue Fern Printing", "Northside Electrical", "Kopi Corner", "Lumen Web Hosting",
           "Greenway Cleaning", "Atlas Office Supply")

def invoices():  # -> [(file name, vendor, date, total, text)]
    r, out, used = rng(51), [], set()
    for i in range(1, 21):
        while True:
            vendor, when = r.choice(VENDORS), date(2025, r.randint(1, 12), r.randint(13, 28))  # day > 12: no
            if (vendor, when) not in used:                                                      # dd/mm doubt
                used.add((vendor, when))
                break
        items = [(r.choice(("Services", "Supplies", "Delivery", "Consulting", "Licence")), round(r.uniform(5, 400),
                                                                                                    2))
                 for _ in range(r.randint(1, 4))]
        total = round(sum(a for _, a in items), 2)
        style = i % 4
        shown = (when.isoformat(), f"{when:%d/%m/%Y}", f"{when.day} {when:%B %Y}", f"{when:%b} {when.day}, "
                 f"{when.year}")[style]
        lines = "\n".join(f"  {name:<20}{amount:>10.2f}" for name, amount in items)
        text = (f"{vendor.upper()}\nINVOICE #{1000 + i}\n\nDate: {shown}\nBill to: Teh Studio\n\n{lines}\n\n"
                + ("Total due: £{:.2f}\n", "AMOUNT DUE {:.2f} GBP\n", "TOTAL  {:.2f}\n", "Please pay £{:.2f}\n")
                [style].format(total) + f"VAT number GB{r.randint(100000000, 999999999)}\n")
        out.append((f"scan{i:02}.txt", vendor, when, total, text))
    return out

def setup(d):
    for name, *_, text in invoices():
        write(d, f"invoices/{name}", text)

def slug(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())

def check(d, answer):
    folder = Path(d, "invoices")
    got = sorted(p.name for p in folder.glob("*.txt") if p.name != "total.txt")
    want = sorted(f"{when.isoformat()}_{vendor.lower().replace(' ', '-')}.txt" for _, vendor, when, _, _ in invoices())
    if sorted(map(slug, got)) != sorted(map(slug, want)):
        return False, f"names differ: missing {sorted(set(want) - set(got))[:3]}, extra {sorted(set(got) - set(want))[:3]}"
    total = round(sum(t for *_, t, _ in invoices()), 2)
    path = folder / "total.txt"
    ok = path.is_file() and has_number(path.read_text(errors="replace"), total, 0.011)
    return ok, f"expected total {total:.2f}"
