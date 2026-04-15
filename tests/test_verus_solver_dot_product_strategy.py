import unittest

from verus_solver.models import VerusResult
from verus_solver.strategies.dot_product import DotProductStrategy


class DotProductStrategyTests(unittest.TestCase):
    def test_injects_lemma_template(self):
        code = """
use vstd::prelude::*;
fn main() {}
verus! {
pub open spec fn partial_dot(a: Seq<u8>, b: Seq<u8>, n: int) -> int
    decreases n
{
    if n <= 0 { 0 }
    else { partial_dot(a, b, n - 1) + a[n - 1] as int * b[n - 1] as int }
}

pub fn dot(a: &[u8], b: &[u8]) -> (result: u32)
    requires a@.len() == b@.len(), a@.len() <= 66051,
    ensures result as int == partial_dot(a@, b@, a@.len() as int),
{
    let mut sum: u32 = 0;
    for i in 0..a.len() {
        sum += (a[i] as u32) * (b[i] as u32);
    }
    sum
}
}
"""
        res = VerusResult(False, 1, 2, False, "", "", [])
        cands = DotProductStrategy().generate(code, res)
        self.assertTrue(cands)
        out = cands[0].code
        self.assertIn("lemma_partial_dot_upper_bound", out)
        self.assertIn("let mut sum: u64 = 0;", out)
        self.assertIn("sum as u32", out)


if __name__ == "__main__":
    unittest.main()

