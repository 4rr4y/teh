import re
from pathlib import Path
from _lib import write, filler, rng

PROMPT = ("What changed between terms_v1.txt and terms_v2.txt? Write changes.md listing each section that was "
          "changed, added or removed, by its number and title, with one line on what changed.")
KIND, SIZE, WEB = "everyday", "long", False

TITLES = ("Definitions", "Eligibility", "Account registration", "Account security", "Subscriptions", "Free trials",
          "Cancellation", "Refunds", "Pricing", "Taxes", "Payment methods", "Late payments", "Acceptable use",
          "Prohibited content", "User submissions", "Licence to us", "Intellectual property", "Trademarks",
          "Third-party services", "Beta features", "Service availability", "Maintenance windows", "Support",
          "Data storage", "Data export", "Data deletion", "Privacy", "Cookies", "Marketing messages",
          "Age requirements", "Fees for premium support", "Promotional codes", "Gift cards", "Referral programme",
          "Suspension", "Termination by you", "Termination by us", "Effect of termination", "Warranties",
          "Disclaimers", "Limitation of liability", "Indemnity", "Force majeure", "Arbitration", "Governing law",
          "Assignment", "Notices", "Entire agreement")
CHANGED = {7: "Cancellation", 15: "User submissions", 22: "Maintenance windows", 31: "Fees for premium support",
           40: "Disclaimers"}
REMOVED = {44: "Arbitration"}
ADDED = {49: "Artificial intelligence features"}

def sections():  # -> (v1, v2): {number: (title, [lines])}
    r = rng(41)
    v1 = {n: (t, filler(r, r.randint(10, 18))) for n, t in enumerate(TITLES, 1)}
    v2 = {n: (t, list(lines)) for n, (t, lines) in v1.items() if n not in REMOVED}
    v1[7][1].insert(3, "You may cancel at any time; cancellation takes effect 30 days after notice.")
    v2[7][1].insert(3, "You may cancel at any time; cancellation takes effect 14 days after notice.")
    v2[15][1].append("We may use your submissions to improve our products, unless you opt out in settings.")
    del v2[22][1][4]
    v1[31][1].insert(2, "Premium support costs £5.00 per ticket.")
    v2[31][1].insert(2, "Premium support costs £7.50 per ticket.")
    v1[40][1].insert(0, "The service is provided as is.")
    v2[40][1].insert(0, "The service is provided as is and as available, without warranties of any kind.")
    v2[49] = (ADDED[49], ["Some features use machine learning; their output may be inaccurate.", *filler(r, 6)])
    return v1, v2

def render(version):
    return "TERMS OF SERVICE\n\n" + "\n".join(f"§ {n}  {title}\n" + "\n".join(lines) + "\n"
                                              for n, (title, lines) in sorted(version.items()))

def setup(d):
    v1, v2 = sections()
    write(d, "terms_v1.txt", render(v1))
    write(d, "terms_v2.txt", render(v2))

def mentioned(text, number, title):
    return title.lower() in text.lower() or re.search(rf"(§|section|clause|^\W*)\s*{number}\b", text, re.I | re.M)

def check(d, answer):
    path = Path(d, "changes.md")
    if not path.is_file():
        return False, "no changes.md"
    text = path.read_text(errors="replace")
    expected = {**CHANGED, **REMOVED, **ADDED}
    missing = [f"{n} {t}" for n, t in expected.items() if not mentioned(text, n, t)]
    unchanged = [t for n, t in enumerate(TITLES, 1) if n not in expected and t.lower() in text.lower()]
    ok = not missing and len(unchanged) <= 4  # a few common words (Support, Pricing) may come up
    return ok, f"missing {missing}" if missing else f"unchanged sections listed: {unchanged}"
