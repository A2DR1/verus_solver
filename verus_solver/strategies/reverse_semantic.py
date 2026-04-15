from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


class ReverseSemanticStrategy(Strategy):
    name = "reverse_semantic"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        if "pub fn reverse(" not in code or "while lo < hi" not in code:
            return cands
        if "forall|k: int| 0 <= k && k < lo ==> a@[k] == old(a)@[n as int - 1 - k]" in code:
            return cands

        patched = code
        old_inv = """        invariant
            a.len() == n,
            n >= 1,
            0 <= lo <= n,
            0 <= hi < n,
            lo <= hi + 1,
        decreases n - lo,
    {"""
        new_inv = """        invariant
            a.len() == n,
            n >= 1,
            0 <= lo <= n,
            lo <= n - lo,
            forall|k: int| 0 <= k && k < lo ==> a@[k] == old(a)@[n as int - 1 - k],
            forall|k: int| n as int - lo <= k && k < n as int ==> a@[k] == old(a)@[n as int - 1 - k],
        decreases n - lo,
    {"""
        patched = patched.replace(old_inv, new_inv)

        # Add explicit semantic bridge after swap.
        marker = "        a[hi] = tmp;\n        lo += 1;"
        if marker in patched:
            patched = patched.replace(
                marker,
                """        a[hi] = tmp;
        proof {
            assert(a@[lo as int] == old(a)@[n as int - 1 - lo as int]);
            assert(a@[hi as int] == old(a)@[n as int - 1 - hi as int]);
        }
        lo += 1;""",
            )

        cands.append(Candidate(name="reverse-prefix-suffix-invariants", code=patched, strategy=self.name))
        return cands

