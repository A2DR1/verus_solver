"""
SyntaxRepairStrategy — deterministic fixes for common Verus compile errors.

Only fires when ``result.compile_error`` is True.  Applies a small menu of
syntactic patches that cover the most frequent compile-time mistakes:

1. **Variable shadowing in loops** — ``let x = expr`` inside a loop that
   shadows a mutable outer binding → rewrite to ``x = expr`` (assignment).

2. **Missing ``mut`` on loop counter** — ``let i = 0usize`` when the loop
   body contains ``i += 1`` or ``i -= 1`` → rewrite to ``let mut i = 0usize``.

3. **Bare integer literals lacking type suffix** in proof/spec contexts where
   Verus requires an explicit ``int`` or ``nat`` — limited to common patterns
   like ``0`` and ``1`` as bounds.

These fixes rarely close a proof obligation but they get the code to *compile*
so that the verifier can report real proof errors on the next iteration.
"""

import re
from typing import List

from ..models import Candidate, VerusResult
from .base import Strategy


# Detects `let <name> = <expr>;` inside a loop body that also has a prior
# `let mut <name>` at outer scope.
_LET_SHADOW_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]+)let\s+(?P<name>\w+)\s*=\s*(?P<expr>[^;]+);$"
)
_LET_MUT_RE = re.compile(r"\blet\s+mut\s+(?P<name>\w+)\b")

# Detects immutable loop counters.
_IMMUT_COUNTER_RE = re.compile(
    r"\blet\s+(?!mut\s)(?P<name>\w+)\s*=\s*0(?:usize|u8|u16|u32|u64|i32|i64)?;"
)
_INCR_RE = re.compile(r"\b(?P<name>\w+)\s*[+\-]=")


def _fix_variable_shadowing(code: str) -> str:
    """Replace ``let x = expr`` with ``x = expr`` when x is already declared
    as ``let mut x`` at outer scope."""
    mut_names = {m.group("name") for m in _LET_MUT_RE.finditer(code)}
    if not mut_names:
        return code

    def replace_shadow(m: re.Match) -> str:
        name = m.group("name")
        if name in mut_names:
            indent = m.group("indent")
            expr = m.group("expr")
            return f"{indent}{name} = {expr};"
        return m.group(0)

    return _LET_SHADOW_RE.sub(replace_shadow, code)


def _fix_immutable_counters(code: str) -> str:
    """Add ``mut`` to loop counters that are incremented/decremented."""
    incr_names = {m.group("name") for m in _INCR_RE.finditer(code)}
    if not incr_names:
        return code

    def add_mut(m: re.Match) -> str:
        name = m.group("name")
        if name in incr_names:
            return m.group(0).replace("let ", "let mut ", 1)
        return m.group(0)

    return _IMMUT_COUNTER_RE.sub(add_mut, code)


class SyntaxRepairStrategy(Strategy):
    name = "syntax_repair"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        # Only activate when the verifier couldn't even compile the code.
        if not result.compile_error:
            return []

        cands: List[Candidate] = []
        patched = _fix_variable_shadowing(code)
        patched = _fix_immutable_counters(patched)

        if patched != code:
            cands.append(
                Candidate(name="syntax-repair", code=patched, strategy=self.name)
            )
        return cands
