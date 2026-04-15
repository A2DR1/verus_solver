from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


class PostconditionStrategy(Strategy):
    name = "postcond"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        if "sum as int == partial_dot(a@, b@, i as int)," in code and "proof {" not in code:
            patched = code.replace(
                "    sum\n}",
                "    proof {\n        assert(sum as int == partial_dot(a@, b@, a@.len() as int));\n    }\n    sum\n}",
            )
            cands.append(Candidate(name="postcond-exit-bridge", code=patched, strategy=self.name))
        return cands

