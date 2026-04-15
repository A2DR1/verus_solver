import unittest

from verus_solver.error_parser import classify_issue, parse_issues
from verus_solver.models import VerusResult
from verus_solver.triage import top_error_class


class ParserTests(unittest.TestCase):
    def test_parse_and_classify(self):
        stderr = """
error: postcondition not satisfied
  --> /tmp/x.rs:20:1
error: possible arithmetic underflow/overflow
  --> /tmp/x.rs:28:16
"""
        issues = parse_issues(stderr)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].kind, "postcond")
        self.assertEqual(issues[1].kind, "overflow")

    def test_triage_prefers_order(self):
        res = VerusResult(
            success=False,
            verified=0,
            errors=2,
            compile_error=False,
            raw_stdout="",
            raw_stderr="",
            issues=parse_issues(
                "error: precondition not satisfied\n  --> /tmp/x.rs:9:1\nerror: postcondition not satisfied\n  --> /tmp/x.rs:20:1"
            ),
        )
        kind = top_error_class(res, ["postcond", "slice_precond"])
        self.assertEqual(kind, "postcond")


if __name__ == "__main__":
    unittest.main()

