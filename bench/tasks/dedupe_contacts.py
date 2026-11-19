import csv
from pathlib import Path
from _lib import write, rng

PROMPT = ("contacts.csv has duplicates: the same person entered more than once, with differences in capitals, spaces "
          "or phone format (the email address, ignoring capitals and spaces, identifies a person). Write "
          "contacts_clean.csv with the same columns and one row per person.")
KIND, SIZE, WEB = "everyday", "short", False

FIRST = "Ana Ben Chloe Dev Emma Farid Grace Hiro Isla Jun Kofi Lena Mateo Nadia Omar Priya Quinn Rosa Sami Tara".split()
LAST = "Ng Tan Lim Patel Smith Garcia Okafor Kim Novak Silva Rossi Ahmed Chen Murphy Kaur Lopez Dubois Sato".split()

def people():
    r, out, seen = rng(21), [], set()
    while len(out) < 240:
        first, last = r.choice(FIRST), r.choice(LAST)
        email = f"{first}.{last}{r.randint(1, 99)}@example.com".lower()
        if email in seen:
            continue
        seen.add(email)
        out.append((f"{first} {last}", email, f"9{r.randint(1000000, 9999999)}", r.choice(("Singapore", "Penang",
                                                                                         "Jakarta", "Manila"))))
    return out

def rows():
    r, out = rng(22), [list(p) for p in people()]
    for name, email, phone, city in r.sample(people(), 50):
        variant = [name.upper() if r.random() < 0.5 else f" {name}", email.upper() if r.random() < 0.5 else
                   f"{email} ", f"+65 {phone[:4]} {phone[4:]}", city]
        out.insert(r.randint(0, len(out)), variant)
    return out

def setup(d):
    with open(Path(d, "contacts.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "email", "phone", "city"])
        writer.writerows(rows())

def check(d, answer):
    path = Path(d, "contacts_clean.csv")
    if not path.is_file():
        return False, "no contacts_clean.csv"
    data = list(csv.reader(path.read_text(errors="replace").splitlines()))
    if [c.strip().lower() for c in data[0]] != ["name", "email", "phone", "city"]:
        return False, f"header is {data[0]}"
    emails = [row[1].strip().lower() for row in data[1:] if row]
    want = {p[1] for p in people()}
    if len(emails) != len(set(emails)):
        return False, f"{len(emails) - len(set(emails))} duplicates left"
    return set(emails) == want, f"{len(emails)} people, expected {len(want)}"
