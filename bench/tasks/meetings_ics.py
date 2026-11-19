import re
from datetime import datetime, timedelta
from pathlib import Path
from _lib import write

PROMPT = ("Turn the meetings in notes.txt into a calendar file, meetings.ics, that I can import into my calendar: "
          "one event per meeting, with its title, start, end, and location where there is one.")
KIND, SIZE, WEB = "everyday", "short", False

NOTES = """Planning notes - week of Monday 7 December 2026

- Kickoff with Dana: Monday, 9:30 to 10:30, Room 4.
- Budget review: Wednesday at 2pm, 90 minutes (video call, no room).
- Team lunch: Friday 12:15, an hour, at Teh Tarik Cafe on Bencoolen St.

Also: buy a leaving gift for Sam before Thursday (not a meeting).
All times are local time.
"""
EXPECTED = [("20261207T0930", "20261207T1030", "room 4"), ("20261209T1400", "20261209T1530", None),
            ("20261211T1215", "20261211T1315", "teh tarik")]

def setup(d):
    write(d, "notes.txt", NOTES)

def end_from_duration(start, value):  # DURATION:PT1H30M
    m = re.search(r"T(?:(\d+)H)?(?:(\d+)M)?", value.upper())
    if not m or not (m[1] or m[2]) or len(start) < 13:
        return None
    t = datetime.strptime(start[:13], "%Y%m%dT%H%M") + timedelta(hours=int(m[1] or 0), minutes=int(m[2] or 0))
    return t.strftime("%Y%m%dT%H%M")

def check(d, answer):
    path = Path(d, "meetings.ics")
    if not path.is_file():
        return False, "no meetings.ics"
    text = re.sub(r"\r?\n[ \t]", "", path.read_text(errors="replace"))  # unfold continued lines
    if "BEGIN:VCALENDAR" not in text or "END:VCALENDAR" not in text:
        return False, "not a calendar"
    events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S)
    found = []
    for event in events:
        props = {}
        for line in event.strip().splitlines():
            name, _, value = line.partition(":")
            props[name.split(";")[0].upper()] = value.strip()
        start = re.sub(r"[^0-9T]", "", props.get("DTSTART", ""))[:13]
        end = re.sub(r"[^0-9T]", "", props.get("DTEND", ""))[:13] or end_from_duration(start,
                                                                                         props.get("DURATION", ""))
        if not props.get("SUMMARY"):
            return False, "an event has no title"
        found.append((start, end, props.get("LOCATION", "").lower()))
    if len(found) != 3:
        return False, f"{len(found)} events, expected 3"
    for start, end, place in EXPECTED:
        match = [f for f in found if f[0] == start and f[1] == end]
        if not match:
            return False, f"no event from {start} to {end}"
        if place and place not in match[0][2].replace("\\", ""):
            return False, f"event at {start} lacks location {place!r}"
    return True, "3 events as expected"
