import unittest

from verus_solver.models import VerusResult
from verus_solver.strategies.invariant import InvariantStrategy
from verus_solver.strategies.overflow import OverflowStrategy


class StrategyTests(unittest.TestCase):
    def _dummy_result(self):
        return VerusResult(
            success=False,
            verified=1,
            errors=2,
            compile_error=False,
            raw_stdout="",
            raw_stderr="",
            issues=[],
        )

    def test_invariant_strategy_inserts_prefix_invariant(self):
        code = """
use vstd::prelude::*;
fn main() {}
verus! {
pub fn dot(a: &[u8], b: &[u8]) -> (result: u32) {
    let mut sum: u32 = 0;
    for i in 0..a.len() {
        sum += (a[i] as u32) * (b[i] as u32);
    }
    sum
}
}
"""
        cands = InvariantStrategy().generate(code, self._dummy_result())
        self.assertTrue(cands)
        self.assertIn("sum as int == partial_dot", cands[0].code)

    def test_overflow_strategy_widens_accumulator(self):
        code = """
let mut sum: u32 = 0;
sum += (a[i] as u32) * (b[i] as u32);
sum
"""
        cands = OverflowStrategy().generate(code, self._dummy_result())
        merged = "\n".join(c.code for c in cands)
        self.assertIn("let mut sum: u64 = 0;", merged)


if __name__ == "__main__":
    unittest.main()

