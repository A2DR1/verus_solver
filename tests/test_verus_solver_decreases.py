import unittest

from verus_solver.models import VerusResult
from verus_solver.strategies.decreases import DecreasesStrategy


class DecreasesStrategyTests(unittest.TestCase):
    def test_adds_decreases_for_lo_hi_loop(self):
        code = """
while lo < hi {
    let hi = n - 1 - lo;
    lo += 1;
}
"""
        res = VerusResult(False, 0, 0, True, "", "error: loop must have a decreases clause", [])
        cands = DecreasesStrategy().generate(code, res)
        self.assertTrue(cands)
        self.assertIn("decreases hi - lo", cands[0].code)


if __name__ == "__main__":
    unittest.main()

