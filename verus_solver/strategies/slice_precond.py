from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


class SlicePrecondStrategy(Strategy):
    name = "slice_precond"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        target = "for i in 0..a.len() {"
        if target in code and "a.len() == b.len()," not in code:
            new_code = code.replace(
                target,
                "for i in 0..a.len()\n        invariant\n            0 <= i <= a.len(),\n            a.len() == b.len(),\n    {",
            )
            cands.append(Candidate(name="slice-precond-loopinv", code=new_code, strategy=self.name))
        return cands

