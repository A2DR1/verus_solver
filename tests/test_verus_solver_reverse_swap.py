import unittest

from verus_solver.models import VerusResult
from verus_solver.strategies.reverse_swap import ReverseSwapStrategy


class ReverseSwapStrategyTests(unittest.TestCase):
    def test_adds_bounds_and_decreases(self):
        code = """
pub fn reverse(a: &mut [i32]) {
    let mut lo = 0usize;
    let mut hi = a.len() - 1;
    let n = a.len();
    while lo < hi {
        let hi = n - 1 - lo;
        let tmp = a[lo];
        a[lo] = a[hi];
        a[hi] = tmp;
        lo += 1;
    }
}
"""
        res = VerusResult(False, 0, 0, True, "", "error: loop must have a decreases clause", [])
        cands = ReverseSwapStrategy().generate(code, res)
        self.assertTrue(cands)
        out = cands[0].code
        self.assertIn("decreases n - lo", out)
        self.assertIn("assert(lo < n);", out)
        self.assertIn("assert(0 <= hi < n);", out)


if __name__ == "__main__":
    unittest.main()

