"""
StructuralLoopInvariantStrategy — parameterized structural frame for while loops.

Complements SlicePrecondStrategy (which handles for-loops) by targeting
``while <lhs> <op> <rhs>`` loops.  It injects:

    invariant
        0 <= <lhs>,
        <lhs> <= <rhs>,      # for < / <=
        <lhs> + <rhs> == <const>,  # if sum-is-const pattern detected (reverse-style)

plus the ``decreases`` clause (if not already present).  It intentionally does
NOT synthesize semantic ``forall`` invariants — that is left for the LLM.
"""

import re
from typing import List, Optional, Tuple

from ..models import Candidate, VerusResult
from .base import Strategy

_WHILE_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)while\s+(?P<lhs>\w+)\s*(?P<op><|<=|>|>=)\s*(?P<rhs>[\w]+(?:\.[\w]+\(\))?)\s*\{"
)

_HAS_INVARIANT_RE = re.compile(r"while\s+\w+\s*[<>=!]+\s*[\w.()]+\s*\n\s*invariant")
_HAS_DECREASES_RE = re.compile(r"while\s+\w+\s*[<>=!]+\s*[\w.()]+\s*(?:\n\s*invariant[^{]*)?\n\s*decreases")


def _already_has_invariant(code: str, m: re.Match) -> bool:
    after = code[m.end():]
    return bool(re.match(r"\s*\n\s*invariant", after))


def _already_has_decreases(code: str, m: re.Match) -> bool:
    after = code[m.end():]
    # Check within the next ~300 chars (before body opens)
    before_body = after.split("{")[0]
    return "decreases" in before_body


def _decreases_expr(lhs: str, op: str, rhs: str) -> str:
    return f"{rhs} - {lhs}" if op in ("<", "<=") else f"{lhs} - {rhs}"


def _bounds_invariants(lhs: str, op: str, rhs: str) -> List[str]:
    """Return structural bound clauses appropriate for the loop condition."""
    if op in ("<", "<="):
        return [f"0 <= {lhs}", f"{lhs} <= {rhs}"]
    else:
        return [f"0 <= {rhs}", f"{rhs} <= {lhs}"]


class StructuralLoopInvariantStrategy(Strategy):
    name = "structural_loop_inv"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        matches = [m for m in _WHILE_RE.finditer(code) if not _already_has_invariant(code, m)]
        if not matches:
            return cands

        patched = code
        for m in reversed(matches):
            indent = m.group("indent")
            lhs = m.group("lhs")
            op = m.group("op")
            rhs = m.group("rhs")

            bounds = _bounds_invariants(lhs, op, rhs)
            expr = _decreases_expr(lhs, op, rhs)
            need_decreases = not _already_has_decreases(code, m)

            inv_block = f"{indent}while {lhs} {op} {rhs}\n"
            inv_block += f"{indent}    invariant\n"
            for b in bounds:
                inv_block += f"{indent}        {b},\n"
            if need_decreases:
                inv_block += f"{indent}    decreases {expr},\n"
            inv_block += f"{indent}{{"

            patched = patched[: m.start()] + inv_block + patched[m.end():]

        if patched != code:
            cands.append(
                Candidate(name="structural-while-inv", code=patched, strategy=self.name)
            )
        return cands
