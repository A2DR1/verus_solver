from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


REVERSE_STEP_LEMMA = """
proof fn lemma_reverse_step(a: Seq<i32>, lo: int, n: int)
    requires
        n == a.len(),
        0 <= lo < n,
        lo <= n - 1 - lo,
    ensures
        true,
{
    // Placeholder lemma skeleton for swap-step reasoning.
}
""".strip()


class ReverseStepLemmaStrategy(Strategy):
    name = "reverse_step_lemma"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        if "pub fn reverse(" not in code or "while lo <" not in code:
            return cands

        patched = code
        if "lemma_reverse_step(" not in patched:
            insert_at = patched.find("pub fn reverse(")
            if insert_at != -1:
                patched = patched[:insert_at] + REVERSE_STEP_LEMMA + "\n\n" + patched[insert_at:]

        marker = "        let tmp = a[lo];"
        if marker in patched and "lemma_reverse_step(a@" not in patched:
            patched = patched.replace(
                marker,
                "        proof { lemma_reverse_step(a@, lo as int, n as int); }\n" + marker,
            )

        if patched != code:
            cands.append(Candidate(name="reverse-step-lemma", code=patched, strategy=self.name))
        return cands

