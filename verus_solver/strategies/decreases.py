from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


class DecreasesStrategy(Strategy):
    name = "decreases"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        if "while lo < hi {" in code and "decreases hi - lo" not in code:
            patched = code.replace("while lo < hi {", "while lo < hi\n        decreases hi - lo,\n    {")
            cands.append(Candidate(name="decreases-hi-lo", code=patched, strategy=self.name))
        if "while i < " in code and "decreases" not in code:
            patched = code.replace("while i < a.len() {", "while i < a.len()\n        decreases a.len() - i,\n    {")
            if patched != code:
                cands.append(Candidate(name="decreases-len-i", code=patched, strategy=self.name))
        return cands

