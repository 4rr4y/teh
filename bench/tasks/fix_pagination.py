from pathlib import Path
from _lib import write, python, run
import sys

PROMPT = "The tests in this project fail. Fix the bug in the code, not the tests."
KIND, SIZE, WEB = "dev", "short", False

CODE = '''"""Splitting lists into pages."""


def paginate(items, page, per_page=10):
    """The items on page `page` (counting from 1), and the number of pages (at least 1)."""
    if per_page < 1:
        raise ValueError("per_page must be at least 1")
    pages = len(items) // per_page
    if page < 1 or page > pages:
        raise IndexError(f"page {page} out of range 1-{pages}")
    start = page * per_page
    return items[start:start + per_page], pages
'''
TESTS = '''import unittest
from pagination import paginate


class TestPaginate(unittest.TestCase):
    def test_first_page(self):
        self.assertEqual(paginate(list(range(25)), 1), (list(range(10)), 3))

    def test_last_page_is_partial(self):
        self.assertEqual(paginate(list(range(25)), 3), ([20, 21, 22, 23, 24], 3))

    def test_empty_list_has_one_page(self):
        self.assertEqual(paginate([], 1), ([], 1))

    def test_out_of_range(self):
        with self.assertRaises(IndexError):
            paginate([1, 2, 3], 2)


if __name__ == "__main__":
    unittest.main()
'''
HIDDEN = '''
from pagination import paginate
assert paginate(list(range(20)), 2, 10) == (list(range(10, 20)), 2)
assert paginate(list(range(21)), 3, 10) == ([20], 3)
assert paginate(["a"], 1, 5) == (["a"], 1)
for bad in (0, 2):
    try:
        paginate(["a"], bad, 5)
        raise SystemExit(f"page {bad} accepted")
    except IndexError:
        pass
print("ok")
'''

def setup(d):
    write(d, "pagination.py", CODE)
    write(d, "test_pagination.py", TESTS)

def check(d, answer):
    if Path(d, "test_pagination.py").read_text() != TESTS:
        return False, "the tests were changed"
    code, out = run([sys.executable, "-B", "-m", "unittest", "-q"], d)
    if code != 0:
        return False, "tests fail: " + out[-300:]
    code, out = python(HIDDEN, d)
    return code == 0, out[-300:]

