import re
import unittest
from pathlib import Path

from tests.helpers import output

EXAMPLES = Path(__file__).parent.parent / "examples"


class TestExamples(unittest.TestCase):
    def test_examples(self):
        expected = re.split(r"^== (\S+)\n", (EXAMPLES / "expected.txt").read_text(), flags=re.M)[1:]
        for name, text in zip(expected[::2], expected[1::2]):
            with self.subTest(name):
                self.assertEqual(output((EXAMPLES / name).read_text()), text.splitlines())
