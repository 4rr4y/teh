import csv, io
from pathlib import Path
from _lib import write

PROMPT = ("Write one letter per person in people.csv, from template.txt, filling in the bracketed fields from the "
          "CSV. Save each in letters/ as first_last.txt, in lower case with any spaces in a name replaced by hyphens "
          "(e.g. letters/anna_van-dijk.txt). Skip anyone whose status is declined.")
KIND, SIZE, WEB = "everyday", "short", False

TEMPLATE = """Dear [First name],

Thank you for registering for [Event]. We look forward to seeing you on [Date] at [Venue].

Your ticket number is [Ticket]; please bring it with you.

Kind regards,
The Events Team
"""
PEOPLE = """first_name,last_name,event,date,venue,ticket,status
Anna,van Dijk,Harbour Lights Gala,Saturday 6 June,"Pier 3, Marina Bay",T-1041,confirmed
Ben,Okafor,Harbour Lights Gala,Saturday 6 June,"Pier 3, Marina Bay",T-1042,confirmed
Chloe,Tan,Design Day,Friday 12 June,The Old School Hall,T-2001,declined
Dev,Patel,Design Day,Friday 12 June,The Old School Hall,T-2002,confirmed
Mary Jane,Lim,Design Day,Friday 12 June,The Old School Hall,T-2003,confirmed
Farid,Ahmed,Harbour Lights Gala,Saturday 6 June,"Pier 3, Marina Bay",T-1043,declined
Grace,Murphy,Book Club Live,Thursday 18 June,Library Room B,T-3001,confirmed
Hiro,Sato,Book Club Live,Thursday 18 June,Library Room B,T-3002,confirmed
Isla,Novak,Book Club Live,Thursday 18 June,Library Room B,T-3003,declined
José,García,Design Day,Friday 12 June,The Old School Hall,T-2004,confirmed
"""

def setup(d):
    write(d, "template.txt", TEMPLATE)
    write(d, "people.csv", PEOPLE)

def check(d, answer):
    want = {}
    for p in csv.DictReader(io.StringIO(PEOPLE)):
        if p["status"] == "declined":
            continue
        name = f"{p['first_name']}_{p['last_name']}".lower().replace(" ", "-") + ".txt"
        want[name] = (TEMPLATE.replace("[First name]", p["first_name"]).replace("[Event]", p["event"])
                      .replace("[Date]", p["date"]).replace("[Venue]", p["venue"]).replace("[Ticket]", p["ticket"]))
    folder = Path(d, "letters")
    got = {p.name for p in folder.glob("*")} if folder.is_dir() else set()
    if got != set(want):
        return False, f"missing {sorted(set(want) - got)}, extra {sorted(got - set(want))}"
    for name, text in want.items():
        if (folder / name).read_text(errors="replace").strip() != text.strip():
            return False, f"{name} differs from the expected letter"
    return True, f"{len(want)} letters"
