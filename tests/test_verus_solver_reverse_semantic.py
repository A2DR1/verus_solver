import unittest

from verus_solver.models import VerusResult
from verus_solver.strategies.reverse_semantic import ReverseSemanticStrategy


class ReverseSemanticStrategyTests(unittest.TestCase):
    def test_adds_prefix_suffix_semantic_invariants(self):
        code = """
pub fn reverse(a: &mut [i32]) {
    let mut lo = 0usize;
    let mut hi = a.len() - 1;
    let n = a.len();
    while lo < hi
        invariant
            a.len() == n,
            n >= 1,
            0 <= lo <= n,
            0 <= hi < n,
            lo <= hi + 1,
        decreases n - lo,
    {
        let hi = n - 1 - lo;
        let tmp = a[lo];
        a[lo] = a[hi];
        a[hi] = tmp;
        lo += 1;
    }
}
"""
        res = VerusResult(False, 1, 1, False, "", "error: postcondition not satisfied", [])
        cands = ReverseSemanticStrategy().generate(code, res)
        self.assertTrue(cands)
        out = cands[0].code
        self.assertIn("forall|k: int| 0 <= k && k < lo", out)
        self.assertIn("forall|k: int| n as int - lo <= k", out)


if __name__ == "__main__":
    unittest.main()

