import unittest
from pathlib import Path

from verus_solver.error_parser import parse_issues


class RegressionFixtureTests(unittest.TestCase):
    def test_overflow_fixture_classification(self):
        text = Path("tests/fixtures/verus_overflow_stderr.txt").read_text()
        issues = parse_issues(text)
        self.assertTrue(any(i.kind == "overflow" for i in issues))

    def test_postcond_fixture_classification(self):
        text = Path("tests/fixtures/verus_postcond_stderr.txt").read_text()
        issues = parse_issues(text)
        self.assertTrue(any(i.kind == "postcond" for i in issues))


if __name__ == "__main__":
    unittest.main()

