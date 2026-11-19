import re
from _lib import write

PROMPT = ("This project has two test suites, tests_api and tests_ui. Each takes about half a minute: run "
          "`python3 -m unittest discover -s tests_api -t .` and the same for tests_ui, and tell me which tests fail.")
KIND, SIZE, WEB = "dev", "slow", False

# Each suite: a slow but passing test (it waits, like a test against a slow service) and one that fails
SUITE = '''import time
import unittest


class Test{name}(unittest.TestCase):
    def test_slow_path(self):
        time.sleep(28)

    def test_{failing}(self):
        self.assertEqual({got}, {want})

    def test_{passing}(self):
        self.assertTrue(True)
'''

def setup(d):
    write(d, "tests_api/__init__.py", "")
    write(d, "tests_api/test_api.py", SUITE.format(name="Api", failing="pagination_cursor", got=20, want=25,
                                                    passing="health_check"))
    write(d, "tests_ui/__init__.py", "")
    write(d, "tests_ui/test_ui.py", SUITE.format(name="Ui", failing="dark_mode_toggle", got='"light"', want='"dark"',
                                                  passing="renders_title"))

def check(d, answer):
    named = {t: bool(re.search(t, answer)) for t in ("pagination_cursor", "dark_mode_toggle")}
    wrong = [t for t in ("health_check", "renders_title", "slow_path")
             if re.search(rf"{t}[^\n]*\b(fail|FAIL)", answer)]
    ok = all(named.values()) and not wrong
    return ok, f"named: {named}; passing tests called failing: {wrong}"
