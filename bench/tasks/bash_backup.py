from pathlib import Path
from _lib import write, run

PROMPT = "backup.sh breaks when file or folder names have spaces in them. Fix it."
KIND, SIZE, WEB = "dev", "short", False

SCRIPT = r"""#!/bin/bash
# Copies every .txt file in SOURCE into a dated folder in DEST.
# usage: backup.sh SOURCE DEST
src=$1
dest=$2/backup-$(date +%Y%m%d)
mkdir -p $dest
for f in $(ls $src/*.txt); do
    cp $f $dest/
    echo "backed up $(basename $f)"
done
echo "done: $(ls $dest | wc -l) files"
"""

def setup(d):
    write(d, "backup.sh", SCRIPT)
    write(d, "docs/readme.txt", "example file\n")

def check(d, answer):
    src = Path(d, ".check/my notes")
    for name in ("a b.txt", "c.txt", "d  e f.txt", "skip.md"):
        write(src, name, f"{name}\n")
    code, out = run(["bash", "backup.sh", str(src), str(Path(d, ".check/my backups"))], d)
    if code != 0:
        return False, f"exit {code}: {out[-300:]}"
    backups = list(Path(d, ".check/my backups").glob("backup-*"))
    if len(backups) != 1:
        return False, f"backup folders: {backups}"
    got = sorted(p.name for p in backups[0].iterdir())
    want = ["a b.txt", "c.txt", "d  e f.txt"]
    ok = got == want and all((backups[0] / n).read_text() == f"{n}\n" for n in want)
    return ok, f"copied {got}, expected {want}"
