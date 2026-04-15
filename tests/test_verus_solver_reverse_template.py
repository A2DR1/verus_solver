import unittest

from verus_solver.models import VerusResult
from verus_solver.strategies.reverse_template import ReverseTemplateStrategy


class ReverseTemplateStrategyTests(unittest.TestCase):
    def test_replaces_reverse_function(self):
        code = """
pub fn reverse(a: &mut [i32]) {
    let mut lo = 0usize;
    let mut hi = a.len() - 1;
    while lo < hi {
        lo += 1;
    }
}
"""
        res = VerusResult(False, 0, 0, True, "", "", [])
        cands = ReverseTemplateStrategy().generate(code, res)
        self.assertTrue(cands)
        out = cands[0].code
        self.assertIn("while lo < hi", out)
        self.assertIn("lo + hi + 1 == n", out)
        self.assertIn("decreases n - lo", out)


if __name__ == "__main__":
    unittest.main()

