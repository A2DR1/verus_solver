import unittest

from verus_solver.models import VerusResult
from verus_solver.scorer import score_result


class ScoringTests(unittest.TestCase):
    def test_score_prefers_more_verified_fewer_errors(self):
        a = VerusResult(True, 4, 0, False, "", "", [])
        b = VerusResult(False, 2, 1, False, "", "", [])
        self.assertGreater(score_result(a), score_result(b))

    def test_compile_error_penalty(self):
        a = VerusResult(False, 0, 0, True, "", "", [])
        b = VerusResult(False, 0, 2, False, "", "", [])
        self.assertLess(score_result(a), score_result(b))


if __name__ == "__main__":
    unittest.main()

