import unittest

from verus_solver.models import VerusResult
from verus_solver.strategies.reverse_step_lemma import ReverseStepLemmaStrategy


class ReverseStepLemmaStrategyTests(unittest.TestCase):
    def test_injects_step_lemma_and_call(self):
        code = """
pub fn reverse(a: &mut [i32]) {
    let n = a.len();
    let mut lo = 0usize;
    while lo < n - lo - 1 {
        let hi = n - 1 - lo;
        let tmp = a[lo];
        a[lo] = a[hi];
        a[hi] = tmp;
        lo += 1;
    }
}
"""
        res = VerusResult(False, 1, 1, False, "", "error: postcondition not satisfied", [])
        cands = ReverseStepLemmaStrategy().generate(code, res)
        self.assertTrue(cands)
        out = cands[0].code
        self.assertIn("proof fn lemma_reverse_step", out)
        self.assertIn("lemma_reverse_step(a@, lo as int, n as int)", out)


if __name__ == "__main__":
    unittest.main()

