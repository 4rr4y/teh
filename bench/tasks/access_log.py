import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from _lib import write, numbers, rng

PROMPT = ("Our website had problems at some point; the server's log is access.log. Write incident.md saying which "
          "hour (date and hour, UTC) had the most 5xx responses and how many there were in that hour, and which "
          "client IP address got the most 5xx responses over the whole log.")
KIND, SIZE, WEB = "everyday", "long", False

PATHS = ("/", "/products", "/products/42", "/cart", "/checkout", "/api/stock", "/login", "/static/app.js")
AGENTS = ("Mozilla/5.0 (X11; Linux x86_64)", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4)", "curl/8.5.0")

def lines():  # -> [(ip, datetime, status)], and the log text
    r, out = rng(7), []
    ips = [f"10.{r.randint(0, 255)}.{r.randint(0, 255)}.{r.randint(1, 254)}" for _ in range(300)]
    start = datetime(2025, 3, 12)
    for _ in range(60_000):
        t = start + timedelta(seconds=r.randint(0, 3 * 86400 - 1))
        ip, status = r.choice(ips), r.choice((200,) * 40 + (304, 301, 404))
        if r.random() < 0.004:
            status = r.choice((500, 502, 503))
        if t.day == 13 and t.hour == 9 and r.random() < 0.25:  # the incident: an hour of 503s
            status = 503
        out.append((ip, t, status))
    for _ in range(700):  # a broken client retrying all the time: the most 5xx overall
        out.append(("198.51.100.23", start + timedelta(seconds=r.randint(0, 3 * 86400 - 1)), 500))
    out.sort(key=lambda x: x[1])
    return out

def setup(d):
    r = rng(8)
    write(d, "access.log", "".join(
        f'{ip} - - [{t:%d/%b/%Y:%H:%M:%S} +0000] "GET {r.choice(PATHS)} HTTP/1.1" {s} {r.randint(200, 9000)} '
        f'"-" "{r.choice(AGENTS)}"\n' for ip, t, s in lines()))

def check(d, answer):
    report = Path(d, "incident.md")
    if not report.is_file():
        return False, "no incident.md"
    text = report.read_text(errors="replace")
    errors = [(ip, t) for ip, t, s in lines() if s >= 500]
    (hour, count), = Counter(t.strftime("%Y-%m-%d %H") for _, t in errors).most_common(1)
    (ip, _), = Counter(ip for ip, _ in errors).most_common(1)
    day_ok = re.search(r"2025-03-13|13/Mar|13(th)? Mar|Mar\w* 13|2025/03/13|03/13", text, re.I)
    hour_ok = re.search(r"\b0?9(:00|:\d\d|\s*(am|h|o'clock|UTC))|\b0?9\s*(-|–|to)\s*10\b|\b09\b", text, re.I)
    ok = hour == "2025-03-13 09" and bool(day_ok and hour_ok) and count in numbers(text) and ip in text
    return ok, f"expected {hour}h with {count} 5xx, and {ip}"
