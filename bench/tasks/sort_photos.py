from pathlib import Path
from _lib import write, rng

PROMPT = ("Sort the photos and videos in photos/ into folders by the year and month they were taken, like "
          "photos/2024/03/, using the date in each file's name. Files with no date in their name go in "
          "photos/unsorted/. Leave notes.txt where it is.")
KIND, SIZE, WEB = "everyday", "short", False

def files():  # -> {name: (year, month) or None}
    r, out = rng(5), {}
    for i in range(24):
        y, m, day = r.choice((2023, 2024)), r.randint(1, 12), r.randint(1, 28)
        out[f"IMG_{y}{m:02}{day:02}_{r.randint(70000, 235959):06}.jpg"] = (y, m)
    for i in range(4):
        y, m = 2024, r.randint(1, 12)
        out[f"VID_{y}{m:02}{r.randint(1, 28):02}_{r.randint(100000, 235959)}.mp4"] = (y, m)
    out["Screenshot 2024-05-02 at 10.11.12.png"] = (2024, 5)
    out["Screenshot 2023-11-19 at 21.03.44.png"] = (2023, 11)
    for name in ("DSC0001.JPG", "DSC0002.JPG", "holiday.jpeg"):
        out[name] = None
    return out

def setup(d):
    for name in files():
        write(d, f"photos/{name}", f"contents of {name}\n")
    write(d, "photos/notes.txt", "Remember to back these up.\n")

def check(d, answer):
    photos = Path(d, "photos")
    for name, when in files().items():
        where = photos / "unsorted" / name if when is None else photos / str(when[0]) / f"{when[1]:02}" / name
        if not where.is_file() or where.read_text() != f"contents of {name}\n":
            return False, f"missing or changed: {where.relative_to(d)}"
    if not (photos / "notes.txt").is_file():
        return False, "notes.txt was moved"
    count = sum(1 for p in photos.rglob("*") if p.is_file())
    return count == len(files()) + 1, f"{count} files under photos/, expected {len(files()) + 1}"
