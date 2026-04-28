"""
SlicePrecondStrategy — variable-name–agnostic structural loop precondition.

Fires on any ``for <idx> in 0..<arr>.len() {`` that lacks an ``invariant``
block, injects the minimal structural frame:

    invariant
        0 <= <idx> <= <arr>.len(),
        <arr>.len() == <other>.len(),   # only if a second slice param exists

Unlike the old version this does NOT hardcode the variable names ``a``, ``b``,
or ``i``, so it fires on ``first_negative``, ``max_even_indexed``, every
CloverBench task, etc.
"""

import re
from typing import List, Optional

from ..models import Candidate, VerusResult
from .base import Strategy

# Matches:  (indent) for <idx> in 0..<arr>.len() {
_FOR_LOOP_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)for\s+(?P<idx>\w+)\s+in\s+0\.\.(?P<arr>\w+)\.len\(\)\s*\{"
)

# Matches a &[...] or &mut [...] parameter in a function signature.
_SLICE_PARAM_RE = re.compile(r"\b(?P<name>\w+)\s*:\s*&(?:mut\s+)?\[")

# Detects an already-present invariant block immediately after the for header.
_HAS_INVARIANT_RE = re.compile(r"for\s+\w+\s+in\s+0\.\.\w+\.len\(\)\s*\n\s*invariant")


def _find_second_slice(code: str, first: str) -> Optional[str]:
    """Return the name of a second &[T] parameter in the nearest fn signature."""
    # Walk backwards from the first for-loop to find the enclosing fn signature.
    fn_re = re.compile(r"(?s)pub(?:\s+open)?\s+(?:fn|spec fn|proof fn)\s+\w+\s*\([^)]*\)")
    params: List[str] = []
    for m in fn_re.finditer(code):
        params = [p.group("name") for p in _SLICE_PARAM_RE.finditer(m.group(0))]
    others = [p for p in params if p != first]
    return others[0] if others else None


def _already_has_invariant(code: str, loop_match: re.Match) -> bool:
    """Return True if the loop at *loop_match* already has an invariant block."""
    after = code[loop_match.end():]
    # Allow optional whitespace / newlines before 'invariant'
    return bool(re.match(r"\s*\n\s*invariant", after))


class SlicePrecondStrategy(Strategy):
    name = "slice_precond"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        matches = [m for m in _FOR_LOOP_RE.finditer(code) if not _already_has_invariant(code, m)]
        if not matches:
            return cands

        patched = code
        # Apply right-to-left so positions stay valid.
        for m in reversed(matches):
            indent = m.group("indent")
            idx = m.group("idx")
            arr = m.group("arr")
            second = _find_second_slice(patched, arr)

            inv_lines = [f"{indent}    invariant"]
            inv_lines.append(f"{indent}        0 <= {idx} <= {arr}.len(),")
            if second:
                inv_lines.append(f"{indent}        {arr}.len() == {second}.len(),")

            original = m.group(0)  # "    for idx in 0..arr.len() {"
            replacement = (
                f"{indent}for {idx} in 0..{arr}.len()\n"
                + "\n".join(inv_lines) + "\n"
                + f"{indent}{{"
            )
            patched = patched[: m.start()] + replacement + patched[m.end():]

        if patched != code:
            cands.append(Candidate(name="slice-precond-loopinv", code=patched, strategy=self.name))
        return cands
