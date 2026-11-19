import csv, io, re
from datetime import date, timedelta
from pathlib import Path
from _lib import write, rng

PROMPT = ("contracts/ has our supplier contracts (with any amendments) and letters/ our letters to and from suppliers. "
          "Today is 1 July 2026. Some contracts renew automatically unless we give notice in time. Make notice.csv "
          "listing every contract whose deadline for giving notice of non-renewal falls between 1 July and 30 "
          "September 2026 (inclusive), with the columns supplier,deadline,annual_fee: deadline the last day we can "
          "give notice (YYYY-MM-DD), annual_fee the yearly fee in pounds as currently agreed. Leave out contracts we "
          "have already given notice on.")
KIND, SIZE, WEB = "everyday", "xl", False

TODAY, WINDOW_END = date(2026, 7, 1), date(2026, 9, 30)
D = date.fromisoformat

# notice: (n, "days" | "weeks" | "months"); fee: (amount, "year" | "quarter" | "month"); renew: months, or 0: none
CONTRACTS = [
    dict(key="Brightway", name="Brightway Cleaning Services Ltd", service="office cleaning", start=D("2024-11-01"),
         months=24, renew=12, notice=(60, "days"), fee=(18500, "year")),
    dict(key="Northgate", name="Northgate IT Support Ltd", service="IT support", start=D("2023-08-15"), months=36,
         renew=12, notice=(90, "days"), fee=(3150, "month")),
    dict(key="Clearwater", name="Clearwater Coolers Ltd", service="the rental and servicing of water coolers",
         start=D("2025-09-01"), months=12, renew=12, notice=(30, "days"), fee=(1840, "year")),
    dict(key="Harbour", name="Harbour Security Group plc", service="manned security and alarm response",
         start=D("2022-01-01"), months=12, renew=12, notice=(4, "months"), fee=(9900, "quarter")),
    dict(key="Pinnacle", name="Pinnacle Print Solutions Ltd", service="the lease and maintenance of printers",
         start=D("2024-04-01"), months=36, renew=12, notice=(90, "days"), fee=(780, "month")),
    dict(key="Greenleaf", name="Greenleaf Interior Plants", service="office plants and their care",
         start=D("2025-01-15"), months=12, renew=12, notice=(30, "days"), fee=(2600, "year")),
    dict(key="Swift", name="Swift Couriers Ltd", service="same-day courier services", start=D("2024-10-01"),
         months=24, renew=0, notice=(60, "days"), fee=(14000, "year")),
    dict(key="Atlas", name="Atlas Telecom Ltd", service="telephone lines and the phone system",
         start=D("2023-10-01"), months=36, renew=12, notice=(60, "days"), fee=(1275, "month")),
    dict(key="Meridian", name="Meridian Payroll Services Ltd", service="payroll processing", start=D("2024-12-01"),
         months=24, renew=12, notice=(30, "days"), fee=(12600, "year")),
    dict(key="Oakridge", name="Oakridge Catering Co.", service="staff restaurant catering", start=D("2025-08-01"),
         months=12, renew=12, notice=(3, "weeks"), fee=(5200, "quarter")),
    dict(key="Vertex", name="Vertex Software Ltd", service="licences for the Vertex CRM system",
         start=D("2025-03-01"), months=12, renew=12, notice=(60, "days"), fee=(22800, "year")),
    dict(key="Bluebell", name="Bluebell Office Supplies Ltd", service="stationery and office supplies",
         start=D("2024-09-01"), months=24, renew=12, notice=(45, "days"), fee=(7300, "year")),
    dict(key="Redline", name="Redline Pest Control Ltd", service="pest control", start=D("2025-10-01"), months=12,
         renew=12, notice=(6, "weeks"), fee=(310, "month")),
    dict(key="Summit", name="Summit Waste Management Ltd", service="waste collection and recycling",
         start=D("2021-07-01"), months=60, renew=12, notice=(6, "months"), fee=(2050, "quarter")),
    dict(key="Lumen", name="Lumen Lighting Maintenance Ltd", service="lighting maintenance", start=D("2024-02-01"),
         months=30, renew=12, notice=(90, "days"), fee=(4400, "year")),
    dict(key="Coastline", name="Coastline Vending Ltd", service="vending machines", start=D("2024-08-01"),
         months=24, renew=12, notice=(60, "days"), fee=(420, "month")),
    dict(key="Keystone", name="Keystone Lifts Ltd", service="lift maintenance", start=D("2023-11-01"), months=36,
         renew=24, notice=(90, "days"), fee=(3600, "quarter")),
    dict(key="Fairway", name="Fairway Grounds Maintenance", service="grounds maintenance", start=D("2025-05-15"),
         months=18, renew=12, notice=(60, "days"), fee=(950, "month")),
    dict(key="Ironclad", name="Ironclad Shredding Ltd", service="confidential document shredding",
         start=D("2024-07-01"), months=24, renew=12, notice=(30, "days"), fee=(3900, "year")),
    dict(key="Sterling", name="Sterling Insurance Brokers Ltd", service="insurance broking", start=D("2025-09-15"),
         months=12, renew=0, notice=(30, "days"), fee=(4200, "year")),
]
# Amendments, in the contract's file unless "file" says otherwise; each changes the fields it names
AMENDMENTS = {
    "Atlas": [dict(signed=D("2025-02-10"), notice=(120, "days"))],
    "Meridian": [dict(signed=D("2025-06-03"), fee=(13860, "year")),
                 dict(signed=D("2026-01-12"), notice=(90, "days"), file=True)],
    "Coastline": [dict(signed=D("2026-03-03"), notice=(14, "days"), fee=(465, "month"))],
    "Sterling": [dict(signed=D("2026-01-20"), renew=12)],
    "Vertex": [dict(signed=D("2025-11-05"), fee=(24600, "year"))],
    "Fairway": [dict(signed=D("2025-09-30"), fee=(1010, "month"), file=True)],
}
TERMINATED = "Bluebell"  # we gave notice by letter


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    days = [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(y, m, min(d.day, days[m - 1]))


def effective(c):
    c = dict(c)
    for a in AMENDMENTS.get(c["key"], []):
        c.update({k: v for k, v in a.items() if k in ("notice", "fee", "renew")})
    return c


def before(end, notice):
    n, unit = notice
    return add_months(end, -n) if unit == "months" else end - timedelta(days=n * (7 if unit == "weeks" else 1))


def deadline(c):  # the next deadline for notice of non-renewal from TODAY on, or None
    c = effective(c)
    if not c["renew"]:
        return None
    k = 0
    while True:
        end = add_months(c["start"], c["months"] + k * c["renew"]) - timedelta(days=1)  # the term's last day
        d = before(end, c["notice"])
        if d >= TODAY:
            return d
        k += 1


def annual(fee):
    amount, per = fee
    return amount * {"year": 1, "quarter": 4, "month": 12}[per]


def expected():  # {key: (deadline, annual fee)}
    out = {}
    for c in CONTRACTS:
        d = deadline(c)
        if d and d <= WINDOW_END and c["key"] != TERMINATED:
            out[c["key"]] = (d, annual(effective(c)["fee"]))
    return out


# ===== Writing the contracts =====
WORDS = {2: "two", 3: "three", 4: "four", 6: "six", 12: "twelve", 14: "fourteen", 18: "eighteen", 21: "twenty-one",
         24: "twenty-four", 30: "thirty", 36: "thirty-six", 45: "forty-five", 60: "sixty", 90: "ninety",
         120: "one hundred and twenty"}

def num(n):
    return f"{WORDS[n]} ({n})" if n in WORDS else str(n)

def notice_text(notice):
    n, unit = notice
    return f"{num(n)} {unit if n != 1 else unit[:-1]}"

def long_date(d, r):
    suffix = "th" if 10 <= d.day % 100 < 20 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
    return r.choice([f"{d.day} {d:%B %Y}", f"the {d.day}{suffix} day of {d:%B %Y}"])

def fee_text(fee):
    amount, per = fee
    return f"£{amount:,} per {per}"

BOILERPLATE = [
    ("Definitions", "In this Agreement, \"Services\" means the services described in clause {services}, \"Charges\" "
     "means the charges set out in clause {charges}, and \"Business Day\" means a day other than a Saturday, a "
     "Sunday or a public holiday in England. Headings are for convenience only and do not affect interpretation. "
     "A reference to a party includes its successors and permitted assigns."),
    ("Standard of the Services", "The Supplier shall perform the Services with reasonable skill and care, in "
     "accordance with good industry practice, and using appropriately qualified and experienced staff. The Supplier "
     "shall comply with the Customer's reasonable site rules, as notified to it from time to time."),
    ("Payment", "The Supplier shall invoice the Customer {billing} in advance. The Customer shall pay each valid "
     "invoice within thirty (30) days of receipt. If any sum is not paid when due, the Supplier may charge interest "
     "at two per cent (2%) a year above the Bank of England base rate until payment is made."),
    ("Changes to the Charges", "The Supplier may increase the Charges once in any twelve (12) month period by giving "
     "the Customer not less than ninety (90) days' written notice of the increase, provided that no increase shall "
     "exceed the rise in the Consumer Prices Index over the preceding twelve months."),
    ("Confidentiality", "Each party shall keep confidential all information of a confidential nature disclosed to it "
     "by the other party, and shall use it only for the purposes of this Agreement. This clause shall survive "
     "termination or expiry of this Agreement for a period of five (5) years."),
    ("Data protection", "Each party shall comply with its obligations under the applicable data protection "
     "legislation. Where the Supplier processes personal data on the Customer's behalf it shall do so only on the "
     "Customer's documented instructions, and shall notify the Customer without undue delay, and in any event within "
     "forty-eight (48) hours, of becoming aware of a personal data breach."),
    ("Liability", "Neither party excludes or limits liability for death or personal injury caused by its negligence, "
     "or for fraud. Subject to that, each party's total liability under this Agreement in any contract year shall "
     "not exceed one hundred and twenty-five per cent (125%) of the Charges paid or payable in that year."),
    ("Insurance", "The Supplier shall maintain public liability insurance of not less than five million pounds "
     "(£5,000,000) and employer's liability insurance as required by law, and shall provide evidence of that "
     "insurance on request."),
    ("Termination for breach", "Either party may terminate this Agreement with immediate effect by written notice if "
     "the other party commits a material breach and, where the breach can be remedied, fails to remedy it within "
     "fourteen (14) days of being notified of it in writing, or if the other party becomes insolvent."),
    ("Force majeure", "Neither party shall be liable for any delay or failure in performing its obligations caused "
     "by events beyond its reasonable control. If such an event continues for more than sixty (60) days, either "
     "party may terminate this Agreement by giving thirty (30) days' written notice to the other."),
    ("Notices", "Any notice under this Agreement shall be in writing and delivered by hand, by recorded post or by "
     "email to the address of the party set out above (or such other address as it has notified). A notice is "
     "deemed received on delivery by hand, two (2) Business Days after posting, or on the next Business Day after "
     "sending by email."),
    ("Assignment and subcontracting", "Neither party may assign or transfer this Agreement without the prior written "
     "consent of the other, such consent not to be unreasonably withheld. The Supplier may subcontract the Services "
     "only with the Customer's written consent and remains responsible for its subcontractors."),
    ("Anti-bribery", "Each party shall comply with the Bribery Act 2010 and shall maintain adequate procedures to "
     "prevent bribery by persons associated with it."),
    ("Health and safety", "The Supplier shall ensure that its personnel comply with all applicable health and safety "
     "legislation while on the Customer's premises, and shall report any accident or near miss to the Customer "
     "within twenty-four (24) hours."),
    ("Variation", "No variation of this Agreement shall be effective unless it is in writing, refers to this "
     "Agreement and is signed by an authorised representative of each party."),
    ("Entire agreement", "This Agreement constitutes the entire agreement between the parties and supersedes all "
     "previous discussions, correspondence and understandings relating to its subject matter."),
    ("Dispute resolution", "The parties shall attempt in good faith to resolve any dispute through their account "
     "managers, and failing that through their senior managers, within thirty (30) days, before starting any court "
     "proceedings."),
    ("Governing law", "This Agreement and any dispute arising from it shall be governed by the law of England and "
     "Wales, and the courts of England and Wales shall have exclusive jurisdiction."),
]
BILLING = {"year": "annually", "quarter": "quarterly", "month": "monthly"}


def contract_text(c, r):
    sections = []  # (heading, text)
    commence = (f"This Agreement commences on {long_date(c['start'], r)} (the \"Commencement Date\") and continues "
                f"for an initial term of {num(c['months'])} months (the \"Initial Term\")")
    if c["renew"]:
        renewal = (f"On the expiry of the Initial Term this Agreement shall renew automatically for successive periods "
                   f"of {num(c['renew'])} months (each a \"Renewal Term\"), unless either party gives the other written "
                   f"notice of non-renewal not less than {notice_text(c['notice'])} before the end of the Initial "
                   f"Term or of the Renewal Term then in force, in which case it shall end at the end of that term.")
    else:
        renewal = ("At the end of the Initial Term this Agreement shall expire automatically and shall not renew. "
                   "Any extension shall be agreed in writing in accordance with the clause on variation.")
    split = r.random() < 0.5  # the renewal provision in its own clause, further on
    sections.append(("Services", f"The Supplier shall provide {c['service']} to the Customer at its premises at 14 "
                                 f"Canal Street, Leeds, as further described in the Supplier's proposal."))
    sections.append(("Term", commence + "." + ("" if split else " " + renewal)))
    sections.append(("Charges", f"In consideration of the Services the Customer shall pay the Supplier "
                                f"{fee_text(c['fee'])}, exclusive of VAT."))
    early = c["key"] == "Swift"
    rest = list(BOILERPLATE)
    r.shuffle(rest)
    sections += rest[:14]
    if early:
        sections.append(("Termination for convenience", f"Either party may terminate this Agreement at any time by "
                                                         f"giving not less than {notice_text(c['notice'])}' written "
                                                         f"notice to the other."))
    if split:
        sections.insert(r.randint(6, len(sections)), ("Duration and renewal", renewal))
    numbers = {h: i + 1 for i, (h, _) in enumerate(sections)}
    body = []
    for i, (heading, text) in enumerate(sections, 1):
        text = text.format(services=numbers["Services"], charges=numbers["Charges"], billing=BILLING[c["fee"][1]])
        body.append(f"{i}. {heading.upper()}\n\n{i}.1 {text}\n")
    signed = c["start"] - timedelta(days=r.randint(10, 40))
    head = (f"SUPPLY OF SERVICES AGREEMENT\n\nThis Agreement is dated {long_date(signed, r)}.\n\nPARTIES\n\n"
            f"(1) Kestrel Home Goods Ltd, of 14 Canal Street, Leeds LS1 4AB (the \"Customer\"); and\n"
            f"(2) {c['name']}, of Unit {r.randint(2, 40)}, {r.choice(['Riverside', 'Westgate', 'Hilltop', 'Station'])}"
            f" Business Park (the \"Supplier\").\n\nIT IS AGREED as follows:\n\n")
    foot = (f"\nSigned for and on behalf of Kestrel Home Goods Ltd: J. Whitfield, Operations Director\n"
            f"Signed for and on behalf of {c['name']}: {r.choice(['A. Patel', 'S. Hughes', 'M. Okafor', 'L. Brennan'])}"
            f", Director\n")
    return head + "\n".join(body) + foot, numbers


def amendment_text(c, n, a, numbers, r):
    lines = [f"AMENDMENT No. {n}", "",
             f"to the Supply of Services Agreement between Kestrel Home Goods Ltd and {c['name']} (the \"Agreement\")",
             "", f"This amendment is signed on {long_date(a['signed'], r)} and takes effect on that date.", ""]
    k = 1
    if "notice" in a:
        clause = numbers.get("Duration and renewal", numbers["Term"])
        lines.append(f"{k}. In clause {clause}, the period of notice of non-renewal is changed to "
                     f"{notice_text(a['notice'])}.")
        k += 1
    if "fee" in a:
        lines.append(f"{k}. In clause {numbers['Charges']}, the Charges are replaced with {fee_text(a['fee'])}, "
                     f"exclusive of VAT.")
        k += 1
    if "renew" in a:
        clause = numbers.get("Duration and renewal", numbers["Term"])
        lines.append(f"{k}. Clause {clause} is amended so that, instead of expiring at the end of the Initial Term, "
                     f"the Agreement shall renew automatically for successive periods of {num(a['renew'])} months, "
                     f"unless either party gives the other written notice of non-renewal not less than "
                     f"{notice_text(c['notice'])} before the end of the term then in force.")
        k += 1
    lines += ["", "All other terms of the Agreement remain unchanged.", "",
              "Signed for Kestrel Home Goods Ltd: J. Whitfield", f"Signed for {c['name']}: Director"]
    return "\n".join(lines) + "\n"


def slug(c):
    return re.sub(r"[^a-z]+", "_", c["name"].lower()).strip("_")


def setup(d):
    r = rng(4102)
    for c in CONTRACTS:
        text, numbers = contract_text(c, r)
        for n, a in enumerate(AMENDMENTS.get(c["key"], []), 1):
            amendment = amendment_text(c, n, a, numbers, r)
            if a.get("file"):
                write(d, f"contracts/{slug(c)}_amendment_{n}.txt", amendment)
            else:
                text += "\n" + "-" * 60 + "\n\n" + amendment
        write(d, f"contracts/{slug(c)}.txt", text)
    write(d, "letters/2026-05-20_bluebell_non_renewal.txt",
          "Kestrel Home Goods Ltd, 14 Canal Street, Leeds LS1 4AB\n\n20 May 2026\n\nBluebell Office Supplies Ltd\n\n"
          "Dear Sirs,\n\nSupply of Services Agreement for stationery and office supplies\n\nWe write to give you "
          "notice, under the Agreement, that we do not wish it to renew at the end of the current term. Please "
          "confirm receipt.\n\nYours faithfully,\nJ. Whitfield, Operations Director\n")
    write(d, "letters/2026-05-27_bluebell_reply.txt",
          "Bluebell Office Supplies Ltd\n\n27 May 2026\n\nDear Mr Whitfield,\n\nThank you for your letter of 20 May. "
          "We confirm receipt of your notice of non-renewal; the Agreement will end on 31 August 2026. We are sorry "
          "to see you go.\n\nYours sincerely,\nAccounts team\n")
    write(d, "letters/2026-04-02_greenleaf_price_increase.txt",
          "Greenleaf Interior Plants\n\n2 April 2026\n\nDear customer,\n\nWe are writing to give you ninety days' "
          "notice of a price increase in line with inflation, under the clause on changes to the charges. From 1 "
          "July 2026 your charges will rise by 3.2%. We will confirm the new amount on your next invoice.\n\n"
          "Kind regards,\nGreenleaf Interior Plants\n")
    write(d, "letters/2026-06-10_northgate_service_review.txt",
          "Kestrel Home Goods Ltd\n\n10 June 2026\n\nDear Northgate,\n\nFurther to our service review, we were "
          "disappointed by the response times in May and would like to discuss them with you. We are considering "
          "our options for when the current term ends.\n\nYours sincerely,\nJ. Whitfield\n")


def check(d, answer):
    path = Path(d, "notice.csv")
    if not path.exists():
        return False, "no notice.csv"
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    header = [h.strip().lower() for h in rows[0]] if rows else []
    if not {"supplier", "deadline", "annual_fee"} <= set(header):
        return False, f"columns are {rows[0] if rows else 'missing'}"
    col = {name: header.index(name) for name in ("supplier", "deadline", "annual_fee")}
    rows = [row for row in rows[1:] if any(c.strip() for c in row)]
    want, wrong = expected(), []
    keys = [c["key"] for c in CONTRACTS]
    found = {}
    for row in rows:
        key = next((k for k in keys if k.lower() in row[col["supplier"]].lower()), None)
        if key is None or key not in want:
            wrong.append(f"shouldn't be listed: {row[col['supplier']]}")
            continue
        found[key] = row
    wrong += [f"missing: {k}" for k in want if k not in found]
    for key, row in found.items():
        due, fee = want[key]
        try:
            got = date.fromisoformat(row[col["deadline"]].strip())
        except ValueError:
            wrong.append(f"{key}: bad date {row[col['deadline']]!r}")
            continue
        if abs((got - due).days) > 3:
            wrong.append(f"{key}: deadline {got}, expected {due}")
        try:
            got_fee = float(re.sub(r"[£,\s]", "", row[col["annual_fee"]]))
        except ValueError:
            got_fee = None
        if got_fee is None or abs(got_fee - fee) > 1:
            wrong.append(f"{key}: fee {row[col['annual_fee']]}, expected {fee}")
    return not wrong, "; ".join(wrong) or "all right"
