from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


class OverflowStrategy(Strategy):
    name = "overflow"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []

        if "let mut sum: u32 = 0;" in code:
            widened = code.replace("let mut sum: u32 = 0;", "let mut sum: u64 = 0;")
            widened = widened.replace("sum += (a[i] as u32) * (b[i] as u32);", "sum += (a[i] as u64) * (b[i] as u64);")
            if "sum as u32" not in widened:
                widened = widened.replace("\n    sum\n}", "\n    sum as u32\n}")
            cands.append(Candidate(name="overflow-widen-accumulator", code=widened, strategy=self.name))

        if "sum as int <= i as int * 65025," not in code and "for i in 0..a.len()" in code:
            with_bound = code.replace(
                "sum as int == partial_dot(a@, b@, i as int),",
                "sum as int == partial_dot(a@, b@, i as int),\n            sum as int <= i as int * 65025,",
            )
            cands.append(Candidate(name="overflow-bound-invariant", code=with_bound, strategy=self.name))

        return cands

