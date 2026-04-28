import re
from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy

# Matches:  (indent) while <lhs> <op> <rhs> {
# rhs may be an identifier or a simple method call like a.len() / n.
# We require the opening brace on the same line to distinguish loop headers
# from multi-line while conditions (rare in Verus, but safe to skip).
_WHILE_COND_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)while\s+"
    r"(?P<lhs>\w+)\s*(?P<op><|<=|>|>=)\s*(?P<rhs>\w+(?:\.\w+\(\))?)\s*\{",
)


def _decreases_expr(lhs: str, op: str, rhs: str) -> str:
    """Infer a termination measure from a simple while-loop condition."""
    if op in ("<", "<="):
        return f"{rhs} - {lhs}"
    else:  # > or >=
        return f"{lhs} - {rhs}"


def _already_annotated(code: str, loop_end: int) -> bool:
    """Return True if there is already a 'decreases' clause between the loop
    header end and the first '{' on the same or next non-blank lines."""
    # Look at up to 400 chars after the header to cover any spec block.
    snippet = code[loop_end : loop_end + 400]
    before_body = snippet.split("{")[0]  # everything before the loop body opens
    return "decreases" in before_body


class DecreasesStrategy(Strategy):
    name = "decreases"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []

        # Collect all un-annotated while loops (in document order).
        matches = [
            m
            for m in _WHILE_COND_RE.finditer(code)
            if not _already_annotated(code, m.end())
        ]
        if not matches:
            return cands

        # Apply patches right-to-left so earlier character positions stay valid.
        patched = code
        for m in reversed(matches):
            indent = m.group("indent")
            lhs = m.group("lhs")
            op = m.group("op")
            rhs = m.group("rhs")
            expr = _decreases_expr(lhs, op, rhs)
            replacement = (
                f"{indent}while {lhs} {op} {rhs}\n"
                f"{indent}    decreases {expr},\n"
                f"{indent}{{"
            )
            patched = patched[: m.start()] + replacement + patched[m.end() :]

        if patched != code:
            cands.append(Candidate(name="decreases-while-loops", code=patched, strategy=self.name))
        return cands
