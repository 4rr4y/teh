import re

PROMPT = ("Find the well-known Stack Overflow question on how to undo the most recent local commits in Git, and tell "
          "me the command its accepted answer recommends for undoing the last commit while keeping the changes.")
KIND, SIZE, WEB = "dev", "short", True

def setup(d):
    pass

def check(d, answer):
    ok = re.search(r"git reset\b.*(HEAD~|HEAD\^|--soft)", answer) is not None
    return ok, "expected git reset HEAD~ (or --soft HEAD~1)"
