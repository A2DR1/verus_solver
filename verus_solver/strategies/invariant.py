from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


class InvariantStrategy(Strategy):
    name = "invariant"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        target = "for i in 0..a.len() {"
        if target in code and "sum as int == partial_dot(a@, b@, i as int)," not in code:
            new_code = code.replace(
                target,
                "for i in 0..a.len()\n        invariant\n            0 <= i <= a.len(),\n            a.len() == b.len(),\n            sum as int == partial_dot(a@, b@, i as int),\n    {",
            )
            cands.append(Candidate(name="invariant-partial-dot", code=new_code, strategy=self.name))
        return cands

