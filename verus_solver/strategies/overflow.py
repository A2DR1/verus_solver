import re
from typing import List, Optional, Tuple

from ..models import Candidate, VerusResult
from .base import Strategy

# Matches "let mut <name>: <type> = 0;" accumulator declarations.
_ACCUM_RE = re.compile(
    r"let\s+mut\s+(?P<var>\w+)\s*:\s*(?P<ty>u8|u16|u32)\s*=\s*0\s*;"
)

# Widening targets: promote to the next unsigned integer width.
_WIDEN: dict = {"u8": "u16", "u16": "u32", "u32": "u64"}


def _widen_accumulator(code: str, var: str, old_ty: str) -> Optional[str]:
    """Return code with the accumulator widened one step, or None if no change."""
    new_ty = _WIDEN[old_ty]
    patched = code.replace(
        f"let mut {var}: {old_ty} = 0;",
        f"let mut {var}: {new_ty} = 0;",
        1,  # replace only the first occurrence
    )
    if patched == code:
        return None

    # Update arithmetic expressions that explicitly cast elements to old_ty.
    # e.g. "(a[i] as u32) * (b[i] as u32)" → "(a[i] as u64) * (b[i] as u64)"
    patched = re.sub(
        rf"\((\w+\[\w+\])\s+as\s+{re.escape(old_ty)}\)",
        rf"(\1 as {new_ty})",
        patched,
    )

    # If the function returns old_ty and the accumulator is returned directly,
    # add a narrowing cast on the return site.
    # Heuristic: "    var\n}" at the end of a function body → "    var as old_ty\n}"
    patched = re.sub(
        rf"\n(\s+){re.escape(var)}\n(\s*\}})",
        rf"\n\1{var} as {old_ty}\n\2",
        patched,
    )
    return patched if patched != code else None


class OverflowStrategy(Strategy):
    name = "overflow"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []

        # Find the first narrow accumulator and widen it.
        m = _ACCUM_RE.search(code)
        if m:
            var = m.group("var")
            old_ty = m.group("ty")
            widened = _widen_accumulator(code, var, old_ty)
            if widened is not None:
                cands.append(
                    Candidate(
                        name=f"overflow-widen-{var}-{old_ty}-to-{_WIDEN[old_ty]}",
                        code=widened,
                        strategy=self.name,
                    )
                )

        return cands
