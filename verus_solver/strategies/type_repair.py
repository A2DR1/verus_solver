"""
TypeRepairStrategy: fix exec-style array indexing used inside proof blocks.

In Verus, proof/spec context requires the sequence-view accessor:
    WRONG:   a[i] as int          (exec indexing)
    CORRECT: a@[i as int] as int  (spec sequence view)

This strategy finds every occurrence of that pattern inside `proof { ... }`
blocks and rewrites it, regardless of the variable names involved.
"""
import re
from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy

# Matches  name[name] as int  — exec-style array indexing cast to int.
_EXEC_IDX_RE = re.compile(r'\b(\w+)\[(\w+)\]\s+as\s+int\b')


def _fix_proof_blocks(code: str) -> str:
    """Replace x[i] as int with x@[i as int] as int inside every proof { } block."""
    parts: list[str] = []
    cursor = 0
    while cursor < len(code):
        start = code.find("proof {", cursor)
        if start == -1:
            parts.append(code[cursor:])
            break
        # Append everything before this proof block unchanged.
        parts.append(code[cursor:start])
        # Find the matching closing brace.
        depth = 0
        j = start
        while j < len(code):
            if code[j] == "{":
                depth += 1
            elif code[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = code[start:j]
        parts.append(_EXEC_IDX_RE.sub(r"\1@[\2 as int] as int", block))
        cursor = j
    return "".join(parts)


class TypeRepairStrategy(Strategy):
    name = "type_repair"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        if "proof {" not in code:
            return cands
        if not _EXEC_IDX_RE.search(code):
            return cands
        patched = _fix_proof_blocks(code)
        if patched != code:
            cands.append(
                Candidate(
                    name="type-proof-index-view",
                    code=patched,
                    strategy=self.name,
                )
            )
        return cands
