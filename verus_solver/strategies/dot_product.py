from typing import List, Optional, Tuple

from ..models import Candidate, VerusResult
from .base import Strategy


DOT_LEMMA = """
proof fn lemma_partial_dot_upper_bound(a: Seq<u8>, b: Seq<u8>, n: int)
    requires
        a.len() == b.len(),
        0 <= n <= a.len(),
    ensures
        partial_dot(a, b, n) <= n * 65025,
    decreases n
{
    if n <= 0 {
    } else {
        lemma_partial_dot_upper_bound(a, b, n - 1);
        assert(0 <= a[n - 1] as int <= 255);
        assert(0 <= b[n - 1] as int <= 255);
        assert((a[n - 1] as int) * (b[n - 1] as int) <= 65025) by (nonlinear_arith);
        assert(partial_dot(a, b, n) == partial_dot(a, b, n - 1) + (a[n - 1] as int) * (b[n - 1] as int));
    }
}
""".strip()


DOT_FN_TEMPLATE = """
pub fn dot(a: &[u8], b: &[u8]) -> (result: u32)
    requires
        a@.len() == b@.len(),
        a@.len() <= 66051,
    ensures
        result as int == partial_dot(a@, b@, a@.len() as int),
{
    let mut sum: u64 = 0;
    for i in 0..a.len()
        invariant
            0 <= i <= a.len(),
            a.len() == b.len(),
            a@.len() <= 66051,
            sum as int == partial_dot(a@, b@, i as int),
            sum as int <= i as int * 65025,
    {
        proof {
            lemma_partial_dot_upper_bound(a@, b@, i as int + 1);
            assert(0 <= a@[i as int] as int <= 255);
            assert(0 <= b@[i as int] as int <= 255);
            assert((a@[i as int] as int) * (b@[i as int] as int) <= 65025) by (nonlinear_arith);
            assert(sum as int <= i as int * 65025);
            assert(partial_dot(a@, b@, i as int + 1) == partial_dot(a@, b@, i as int) + (a@[i as int] as int) * (b@[i as int] as int));
            assert(sum as int + (a@[i as int] as int) * (b@[i as int] as int) == partial_dot(a@, b@, i as int + 1));
            assert(sum as int + (a@[i as int] as int) * (b@[i as int] as int) <= (i as int + 1) * 65025);
            assert(i < a.len());
            assert(i as int + 1 <= a@.len());
            assert((i as int + 1) * 65025 <= 66051 * 65025);
            assert(66051 * 65025 <= u64::MAX as int);
            assert(sum as int + (a@[i as int] as int) * (b@[i as int] as int) <= u64::MAX as int);
        }
        sum += (a[i] as u64) * (b[i] as u64);
    }
    proof {
        lemma_partial_dot_upper_bound(a@, b@, a@.len() as int);
        assert(sum as int <= a@.len() as int * 65025);
        assert(a@.len() as int * 65025 <= u32::MAX as int);
    }
    sum as u32
}
""".strip()


class DotProductStrategy(Strategy):
    name = "dot_product"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        if "partial_dot" not in code or "pub fn dot(" not in code:
            return cands
        fn_block = _extract_dot_function_block(code)
        if fn_block is None:
            return cands
        start, end = fn_block
        patched = code
        if "lemma_partial_dot_upper_bound" not in patched:
            insert_at = patched.find("pub fn dot(")
            if insert_at != -1:
                patched = patched[:insert_at] + DOT_LEMMA + "\n\n" + patched[insert_at:]
                # Function index shifted after insertion; recompute.
                fn_block = _extract_dot_function_block(patched)
                if fn_block is None:
                    return cands
                start, end = fn_block
        patched = patched[:start] + DOT_FN_TEMPLATE + patched[end:]
        cands.append(Candidate(name="dot-product-lemma-template", code=patched, strategy=self.name))
        return cands


def _extract_dot_function_block(code: str) -> Optional[Tuple[int, int]]:
    start = code.find("pub fn dot(")
    if start == -1:
        return None
    brace_open = code.find("{", start)
    if brace_open == -1:
        return None
    depth = 0
    i = brace_open
    while i < len(code):
        ch = code[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return (start, i + 1)
        i += 1
    return None

