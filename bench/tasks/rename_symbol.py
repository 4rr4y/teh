import re, sys
from pathlib import Path
from _lib import write, run, python

PROMPT = ("Rename the function get_usr to get_user everywhere it is used: code, tests and docs. Leave get_usr_count "
          "as it is.")
KIND, SIZE, WEB = "dev", "short", False

FILES = {
    "app/__init__.py": "",
    "app/users.py": '''"""User lookups."""
USERS = {1: {"name": "Ana", "active": True}, 2: {"name": "Ben", "active": False}, 3: {"name": "Chloe", "active": True}}


def get_usr(user_id):
    """The user with this id, or None."""
    return USERS.get(user_id)


def get_usr_count(active_only=False):
    return sum(1 for u in USERS.values() if u["active"] or not active_only)
''',
    "app/api.py": '''from app.users import get_usr, get_usr_count


def handle_get(user_id):
    user = get_usr(user_id)
    if user is None:
        return 404, {"error": f"no user {user_id}"}
    return 200, user


def handle_count():
    return 200, {"count": get_usr_count()}
''',
    "app/admin.py": '''from app import users


def deactivate(user_id):
    user = users.get_usr(user_id)  # get_usr returns the stored dict, so this changes it in place
    if user:
        user["active"] = False
    return user
''',
    "app/reports.py": '''from app.users import get_usr as lookup, get_usr_count


def name_list(ids):
    return [lookup(i)["name"] for i in ids if lookup(i)]


def summary():
    return f"{get_usr_count(active_only=True)} of {get_usr_count()} users active"
''',
    "scripts/export.py": '''import json
import sys

sys.path.insert(0, ".")
from app.users import get_usr  # noqa: E402

print(json.dumps([get_usr(i) for i in (1, 2, 3)]))
''',
    "tests/__init__.py": "",
    "tests/test_users.py": '''import unittest
from app.users import get_usr, get_usr_count


class TestUsers(unittest.TestCase):
    def test_get_usr(self):
        self.assertEqual(get_usr(1)["name"], "Ana")
        self.assertIsNone(get_usr(99))

    def test_count(self):
        self.assertEqual(get_usr_count(), 3)


if __name__ == "__main__":
    unittest.main()
''',
    "docs/api.md": '''# Users API

- `get_usr(user_id)` returns the user, or `None`.
- `get_usr_count(active_only=False)` counts users.

Call get_usr() rather than reading `USERS` directly.
''',
}

def setup(d):
    for name, text in FILES.items():
        write(d, name, text)

def check(d, answer):
    for path in Path(d).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and ".check" not in path.parts:
            text = path.read_text(errors="replace")
            if re.search(r"\bget_usr\b", text):
                return False, f"get_usr is still in {path.relative_to(d)}"
            if path.name in ("users.py", "reports.py", "api.py", "api.md") and "get_usr_count" not in text:
                return False, f"get_usr_count is gone from {path.name}"
    code, out = run([sys.executable, "-B", "-m", "unittest", "-q"], d)
    if code != 0:
        return False, "tests fail: " + out[-300:]
    code, out = python("from app.users import get_user, get_usr_count\nfrom app import api, admin, reports\n"
                       "assert api.handle_get(1)[0] == 200 and reports.name_list([1, 9]) == ['Ana']\n"
                       "assert admin.deactivate(3)['active'] is False", d)
    if code != 0:
        return False, out[-300:]
    code, out = run([sys.executable, "-B", "scripts/export.py"], d)
    return code == 0 and "Ana" in out, f"scripts/export.py: {out[-200:]}"
