from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


class TypeRepairStrategy(Strategy):
    name = "type_repair"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        # Common repair: use sequence-view indexing in proof blocks.
        if "proof {" in code and "a[i] as int" in code:
            patched = code.replace("a[i] as int", "a@[i as int] as int").replace("b[i] as int", "b@[i as int] as int")
            cands.append(Candidate(name="type-proof-index-view", code=patched, strategy=self.name))
        return cands

