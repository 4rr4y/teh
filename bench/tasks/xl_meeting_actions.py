import csv, io, re
from datetime import date, timedelta
from pathlib import Path
from _lib import write, rng

PROMPT = ("notes/ has the notes of our weekly team meeting for the first half of the year. Make actions.csv with one "
          "row per action item agreed in them, and the columns item,owner,due,status: item a short description, owner "
          "who is responsible for it now, due its current due date (YYYY-MM-DD), status open, done or dropped, as of "
          "the latest notes. An action item is a task someone took on; ideas nobody took on don't count.")
KIND, SIZE, WEB = "everyday", "xl", False

FIRST = date(2026, 1, 5)  # a Monday; one meeting a week
MEETINGS = 26
PEOPLE = ["Priya", "Tom", "Aisha", "Marek", "Lena", "Joon", "Carlos", "Hannah"]

# key: (pattern the item's description must match, what to do, what it's called afterwards)
ITEMS = {
    "survey": (r"survey", "draft the vendor survey", "vendor survey"),
    "venue": (r"venue|offsite", "book a venue for the June offsite", "offsite venue booking"),
    "onboarding": (r"onboarding", "update the onboarding checklist", "onboarding checklist"),
    "backup": (r"backup|restore", "test restoring last month's backups", "backup restore test"),
    "budget": (r"budget", "prepare the Q3 budget proposal", "Q3 budget proposal"),
    "laptop": (r"laptop", "order replacement laptops for the support team", "laptop order"),
    "newsletter": (r"newsletter", "redesign the newsletter template", "newsletter redesign"),
    "accessibility": (r"accessib", "run an accessibility audit of the website", "accessibility audit"),
    "handbook": (r"handbook|travel", "review the travel section of the staff handbook", "handbook travel review"),
    "cleaning": (r"cleaning", "renegotiate the cleaning contract", "cleaning contract"),
    "intern": (r"intern", "write the job advert for the summer intern", "intern advert"),
    "dashboard": (r"dashboard", "fix the broken sales dashboard", "sales dashboard"),
    "insurance": (r"insurance", "renew the office insurance", "insurance renewal"),
    "firstaid": (r"first.?aid", "organise first-aid training", "first-aid training"),
    "archive": (r"archiv", "archive the 2022 project files", "2022 archive"),
    "quotes": (r"quote|testimonial|feedback", "collect customer quotes for the website", "customer quotes"),
    "email": (r"e-?mail|migrat", "plan the move to the new email system", "email migration plan"),
    "parking": (r"parking", "sort out parking permits for the new car park", "parking permits"),
}

D = date.fromisoformat
# (meeting, item, event, args): new (owner, due), due (date), owner (new owner[, date]), done, dropped (reason),
# reopen (date), progress (text), relative: a due date said as "Friday next week"
EVENTS = [
    (0, "survey", "new", ("Priya", D("2026-01-30"))), (0, "venue", "new", ("Tom", D("2026-02-13"))),
    (0, "onboarding", "new", ("Aisha", D("2026-01-23"))),
    (1, "backup", "new", ("Marek", "friday next week")), (1, "survey", "progress", "has sent a first draft round"),
    (2, "onboarding", "done", None), (2, "budget", "new", ("Lena", D("2026-03-20"))),
    (3, "survey", "due", D("2026-02-06")), (3, "backup", "failed", D("2026-02-13")),
    (4, "laptop", "new", ("Joon", D("2026-02-27"))), (4, "newsletter", "new", ("Carlos", D("2026-03-13"))),
    (5, "venue", "owner", ("Hannah",)), (5, "survey", "done", None),
    (6, "backup", "done", None), (6, "accessibility", "new", ("Aisha", D("2026-04-10"))),
    (6, "laptop", "helper", "Lena"),
    (7, "venue", "due", D("2026-03-06")), (7, "handbook", "new", ("Priya", D("2026-03-31"))),
    (8, "laptop", "done", None), (8, "cleaning", "new", ("Marek", D("2026-04-30"))),
    (9, "newsletter", "dropped", "it will be rebuilt anyway when we move to the new email system"),
    (9, "venue", "done", None),
    (10, "intern", "new", ("Tom", D("2026-03-27"))), (10, "budget", "owner", ("Carlos", D("2026-03-27"))),
    (11, "dashboard", "new", ("Joon", "friday next week")), (11, "handbook", "progress", "is about half way through"),
    (12, "budget", "done", None), (12, "intern", "done", None),
    (13, "accessibility", "due", D("2026-05-08")), (13, "insurance", "new", ("Hannah", D("2026-04-24"))),
    (14, "dashboard", "done", None), (14, "firstaid", "new", ("Lena", D("2026-05-29"))),
    (14, "handbook", "owner", ("Aisha", D("2026-04-30"))),
    (15, "dashboard", "reopen", D("2026-05-01")), (15, "cleaning", "progress", "has had two quotes back"),
    (16, "insurance", "done", None), (16, "archive", "new", ("Carlos", D("2026-06-12"))),
    (17, "accessibility", "owner", ("Priya", D("2026-05-22"))),
    (18, "handbook", "done", None), (18, "quotes", "new", ("Marek", D("2026-06-05"))),
    (18, "cleaning", "due", D("2026-05-29")),
    (19, "email", "new", ("Tom", D("2026-07-17"))), (19, "accessibility", "progress", "has finished the home page"),
    (20, "cleaning", "progress", "expects the new terms any day now"),
    (21, "firstaid", "done", None), (21, "parking", "new", ("Hannah", D("2026-06-19"))),
    (22, "archive", "owner", ("Joon", D("2026-06-26"))), (22, "quotes", "progress", "has five quotes so far"),
    (23, "quotes", "dropped", "the website relaunch is postponed to next year, so the quotes aren't needed now"),
    (24, "parking", "due", D("2026-07-03")), (24, "email", "progress", "has a first list of mailboxes"),
    (25, "archive", "progress", "has moved about a third of the folders"),
]
IDEAS = {2: "a team podcast", 7: "new plants for the meeting room", 12: "a refreshed company logo",
         19: "a new coffee machine", 25: "a quarterly book club"}


def expected():  # {key: (owner, due, status)}
    state = {}
    for m, key, event, args in EVENTS:
        meeting = FIRST + timedelta(weeks=m)
        if event == "new":
            owner, due = args
            due = meeting + timedelta(days=11) if due == "friday next week" else due
            state[key] = [owner, due, "open"]
        elif event in ("due", "failed", "reopen"):
            state[key][1:] = [args, "open"]
        elif event == "owner":
            state[key][0] = args[0]
            if len(args) > 1:
                state[key][1] = args[1]
        elif event == "done":
            state[key][2] = "done"
        elif event == "dropped":
            state[key][2] = "dropped"
    return {k: tuple(v) for k, v in state.items()}


def when(r, d):  # a date, in one of the ways people write them
    return r.choice([f"{d.day} {d:%B}", f"{d:%B} {d.day}", f"{d:%A} {d.day} {d:%B}", f"{d.day} {d:%b}",
                     f"the {d.day}{'th' if 10 <= d.day % 100 < 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d.day % 10, 'th')}"
                     f" of {d:%B}"])


def sentence(r, m, key, event, args, owners):
    _, task, noun = ITEMS[key]
    owner = owners.get(key)
    if event == "new":
        who, due = args
        due = "Friday next week" if due == "friday next week" else when(r, due)
        return r.choice([f"Action: {who} to {task} by {due}.",
                         f"{who} agreed to {task}, with a target of {due}.",
                         f"We asked {who} to {task}; {who} thinks {due} is realistic.",
                         f"{who} will {task}. Due: {due}."])
    if event == "due":
        return r.choice([f"The {noun} has moved to {when(r, args)}.",
                         f"{owner} asked for more time on the {noun}: the new date is {when(r, args)}.",
                         f"We agreed the {noun} can wait until {when(r, args)}."])
    if event == "failed":
        return (f"{owner} ran the {noun}, but the restore of the mail archive failed. {owner} will repeat it once "
                f"IT has fixed the archive, by {when(r, args)}.")
    if event == "reopen":
        return (f"Bad news on the {noun}: it broke again after last week's data refresh, so it isn't fixed after "
                f"all. {owner} is looking at it again and hopes to be done by {when(r, args)}.")
    if event == "owner":
        new = args[0]
        why = r.choice(["is off on leave for a month", "has been moved onto the warehouse project",
                        "has too much on at the moment"])
        due = (f", and the date moves to {when(r, args[1])}" if len(args) > 1 else ", with the same date")
        return f"{owner} {why}, so {new} takes over the {noun}{due}."
    if event == "done":
        return r.choice([f"{owner} has finished the {noun}.", f"The {noun} is done, thanks to {owner}.",
                         f"{owner} reported that the {noun} is complete."])
    if event == "dropped":
        return f"We're dropping the {noun}: {args}."
    if event == "progress":
        return f"{owner} gave an update on the {noun}: {owner} {args}."
    if event == "helper":
        return f"{args} offered to help {owner} with the {noun}, but it stays with {owner}."
    raise ValueError(event)


FILLER = [
    "The kitchen rota was agreed for the next month, with the usual swaps allowed.",
    "Sales were roughly in line with the forecast, a little ahead in the north and a little behind in the south.",
    "There was a long discussion about whether the Monday meeting should start at half past nine instead; no change "
    "for now.",
    "The fire alarm test is on Wednesday morning, as usual.",
    "Several people said the new expense system is slow to load in the mornings.",
    "The printer on the second floor is out of service again, and the engineer is due later in the week.",
    "Customer support numbers were steady: about the same volume of tickets as the week before, and response times "
    "within target.",
    "The team welcomed the two temporary staff who are helping with the stocktake.",
    "There were questions about the holiday calendar; everyone should check their own entries are right.",
    "The quarterly all-hands is coming up, and the slides are being collected centrally as before.",
    "A reminder that visitors must sign in at reception and wear a badge.",
    "The heating in the east wing has been fixed, according to the building manager.",
    "We went through the risk register; nothing new was added this week.",
    "Feedback on the new desk booking tool has been mostly positive, though some people find the mobile view fiddly.",
    "The charity bake sale raised a little over three hundred pounds.",
    "Someone asked whether the car share scheme is still running; it is, and the sign-up sheet is on the intranet.",
    "The finance team asked that receipts be submitted before the end of the month, not after.",
    "Two customers praised the support team by name this week, which was nice to hear.",
    "We discussed the recent outage of the booking system; the supplier has sent an explanation and a credit.",
    "The meeting room screens still don't always connect to laptops on the first try.",
    "Everyone was reminded to complete the annual data protection refresher.",
    "The warehouse reported that deliveries were on time all week.",
    "There was some debate about the best day for the team lunch, and Thursday won narrowly.",
    "The office will close early on the Friday before the bank holiday.",
    "The recycling bins have been moved next to the lifts.",
    "We looked at the website traffic figures, which were up slightly on the previous month.",
    "The new starter in finance introduced themselves and said hello to everyone.",
    "A few people asked for more standing desks; facilities are keeping a list.",
    "Nothing to report from the health and safety committee this week.",
    "The board meeting went well, and the minutes will be shared once approved.",
    "Wi-fi in the basement meeting rooms is still patchy.",
    "We spent a few minutes on the staff survey results, which will be discussed properly next month.",
    "The post room asked that parcels for individuals not be sent to the office where possible.",
    "There was general agreement that the shorter Friday meetings are working well.",
    "The supplier of the water coolers is changing, with no change for anyone in practice.",
    "Usage of the shared drive is close to its limit, and IT asked people to tidy their own folders.",
    "The phone system update happened over the weekend without problems.",
    "People were asked to keep the quiet room quiet.",
    "We reviewed the complaints log; the two open complaints are with the right people.",
    "The local school asked whether anyone could give a careers talk; a few people said they might.",
    "The team noted that the spring sale starts in two weeks, and stock levels look fine.",
    "Somebody pointed out that the clocks change this month, so meeting invites across time zones may look odd.",
    "The lift on the north side will be serviced next week, and will be out of use for a morning.",
    "There was a brief update on the office move next year: the shortlist of buildings is still being drawn up.",
    "The team thanked everyone who covered the phones during last week's training day.",
    "Visitors next week include two people from the auditors, who will need a desk for three days.",
    "The cleaners asked that desks be cleared on Thursday evenings so they can do a deep clean.",
    "The social committee is collecting ideas for the summer party, and the shortlist will go round by email.",
    "Two laptops were reported stolen from cars in the area, so people were reminded not to leave bags on show.",
    "The sales team shared a short summary of the trade show, which brought in a handful of good leads.",
    "Facilities said the bike racks are full most days, and a second rack has been requested.",
    "There was a question about overtime rules for weekend events; HR will circulate the policy again.",
    "The marketing calendar for the next quarter is in the shared folder for comments.",
    "Somebody asked about the noise from the building work next door; it should finish by the end of the month.",
    "The mentoring scheme has room for three more pairs, and anyone interested should say so.",
    "We noted that two long-standing customers renewed their contracts this week.",
    "The team agreed to keep using the shared inbox for supplier queries, rather than personal ones.",
    "Stock of the most popular product line is low, but the next delivery is already booked.",
    "The intranet search has improved since the update, although old documents still show up first.",
    "Everyone was asked to check that their emergency contact details are up to date.",
    "A visitor left an umbrella in meeting room three; it is at reception.",
    "The quarterly figures will be ready a few days later than usual because of the audit.",
    "IT reminded everyone that passwords now have to be changed every six months rather than every three.",
    "The team discussed how to handle the growing number of calls on Monday mornings, with no decision yet.",
    "There was a short presentation on the results of the customer satisfaction survey from the autumn.",
    "The parcel lockers by the entrance are now working, after a delay.",
    "People were asked to book leave for the summer by the end of next month, to help with planning.",
    "Some of the meeting rooms are being booked and then not used; please cancel bookings you don't need.",
    "The fridge will be emptied on Friday afternoon, so label anything you want to keep.",
    "The finance director thanked the team for getting the year-end numbers in on time.",
    "Feedback from the pilot of hybrid working days is being collected through a short form.",
]
DYNAMIC = [
    lambda r: f"Support closed {r.randint(180, 320)} tickets last week, {r.randint(3, 40)} "
              f"{r.choice(['more', 'fewer'])} than the week before.",
    lambda r: f"Website orders were {r.randint(900, 1600):,} for the week, with an average basket of "
              f"£{r.randint(30, 60)}.{r.randint(10, 99)}.",
    lambda r: f"Staff absence was {r.randint(2, 9)} days in total, mostly colds.",
    lambda r: f"The phone queue peaked at {r.randint(6, 25)} callers on {r.choice(['Monday', 'Tuesday'])} "
              f"morning.",
]

def setup(d):
    r = rng(4101)
    owners = {}
    by_meeting = {}
    for m, key, event, args in EVENTS:
        by_meeting.setdefault(m, []).append((key, event, args))
    for m in range(MEETINGS):
        day = FIRST + timedelta(weeks=m)
        present = sorted(r.sample(PEOPLE, 6))
        lines = [f"# Team meeting, {day:%A} {day.day} {day:%B %Y}", "",
                 f"Present: {', '.join(present)}. Chair: {r.choice(present)}.", ""]
        pool = r.sample(FILLER, len(FILLER)) + [f(r) for f in DYNAMIC]
        r.shuffle(pool)
        paragraphs = []
        while len(pool) >= 4 and len(paragraphs) < r.randint(9, 11):
            paragraphs.append(" ".join(pool.pop() for _ in range(r.randint(4, 6))))
        events = []
        for key, event, args in by_meeting.get(m, []):
            events.append(sentence(r, m, key, event, args, owners))
            if event == "new":
                owners[key] = args[0]
            elif event == "owner":
                owners[key] = args[0]
        if m in IDEAS:
            events.append(f"{r.choice(PEOPLE)} suggested we could look into {IDEAS[m]} at some point. "
                          f"Nobody took it on, so it stays an idea for now.")
        for e in events:  # each into a paragraph, at a random place in it
            i = r.randrange(len(paragraphs))
            parts = re.split(r"(?<=\.) ", paragraphs[i])
            parts.insert(r.randint(0, len(parts)), e)
            paragraphs[i] = " ".join(parts)
        heads = ["## Updates", "## Discussion", "## Any other business"]
        cut = sorted(r.sample(range(1, len(paragraphs)), 2))
        for head, chunk in zip(heads, (paragraphs[:cut[0]], paragraphs[cut[0]:cut[1]], paragraphs[cut[1]:])):
            lines += [head, ""] + [p + "\n" for p in chunk]
        write(d, f"notes/{day:%Y-%m-%d}.md", "\n".join(lines))


def check(d, answer):
    path = Path(d, "actions.csv")
    if not path.exists():
        return False, "no actions.csv"
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    if not rows:
        return False, "actions.csv is empty"
    header = [h.strip().lower() for h in rows[0]]
    if not {"item", "owner", "due", "status"} <= set(header):
        return False, f"columns are {rows[0]}"
    col = {name: header.index(name) for name in ("item", "owner", "due", "status")}
    rows = [row for row in rows[1:] if any(c.strip() for c in row)]
    want = expected()
    if len(rows) != len(want):
        return False, f"{len(rows)} rows, expected {len(want)}"
    wrong = []
    for key, (owner, due, status) in want.items():
        pattern = ITEMS[key][0]
        match = [row for row in rows if re.search(pattern, row[col["item"]], re.I)]
        if len(match) != 1:
            wrong.append(f"{key}: {len(match)} rows")
            continue
        row = match[0]
        got_owner, got_due = row[col["owner"]].strip(), row[col["due"]].strip()
        got_status = row[col["status"]].strip().lower()
        if got_status != status:
            wrong.append(f"{key}: status {got_status}, expected {status}")
        elif status != "dropped" and owner.lower() not in got_owner.lower():
            wrong.append(f"{key}: owner {got_owner}, expected {owner}")
        elif status == "open" and got_due != due.isoformat():
            wrong.append(f"{key}: due {got_due}, expected {due}")
    return not wrong, "; ".join(wrong) or "all right"
