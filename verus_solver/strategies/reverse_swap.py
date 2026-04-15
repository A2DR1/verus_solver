from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


class ReverseSwapStrategy(Strategy):
    name = "reverse_swap"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        if "pub fn reverse(" not in code or "while lo < hi" not in code:
            return cands

        patched = code
        patched = patched.replace(
            "while lo < hi {",
            """while lo < hi
        invariant
            a.len() == n,
            n >= 1,
            0 <= lo <= n,
            0 <= hi < n,
            lo <= hi + 1,
        decreases n - lo,
    {""",
        )
        # Guard arithmetic and indexing obligations explicitly.
        patched = patched.replace(
            "let hi = n - 1 - lo;",
            "assert(lo < n);\n        let hi = n - 1 - lo;\n        assert(0 <= hi < n);",
        )
        if patched != code:
            cands.append(Candidate(name="reverse-bounds-decreases", code=patched, strategy=self.name))
        return cands

