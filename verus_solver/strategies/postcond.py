"""
PostconditionStrategy: bridge a loop's spec-function invariant to the
post-condition by inserting an assert just before the function's return value.

General pattern detected:
  A loop invariant of the form:
      <acc> as int == <spec_fn>(<args>, <idx> as int),
  where <idx> is the loop counter.  At loop exit <idx> == <arr>.len(), so
  the verifier sometimes needs an explicit:
      proof { assert(<acc> as int == <spec_fn>(<args>, <arr>.len() as int)); }
  inserted just before `return <acc>` (or a bare `<acc>` at the end of a fn body).

Variable names are extracted from the code; nothing is hardcoded.
"""
import re
from typing import List, Optional, Tuple

from ..models import Candidate, VerusResult
from .base import Strategy

# Finds:  <acc> as int == <spec_fn>(<args>),
# inside an `invariant` block.
_INV_SPEC_RE = re.compile(
    r"\binvariant\b[^{]*?(\w+)\s+as\s+int\s*==\s*(\w+)\(([^)]+)\)",
    re.DOTALL,
)

# The last <idx> as int argument in a spec-fn call argument list.
_IDX_ARG_RE = re.compile(r"\b(\w+)\s+as\s+int\s*$")


def _extract_bridge_info(code: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Return (acc, spec_fn, full_arg_list_with_idx, idx) if a bridgeable
    invariant is found, otherwise None.
    """
    m = _INV_SPEC_RE.search(code)
    if not m:
        return None
    acc, spec_fn, raw_args = m.group(1), m.group(2), m.group(3)
    # Identify the loop counter: the last argument that matches `<name> as int`.
    args = [a.strip() for a in raw_args.split(",")]
    idx_m = _IDX_ARG_RE.search(args[-1]) if args else None
    if not idx_m:
        return None
    idx = idx_m.group(1)
    return acc, spec_fn, raw_args, idx


def _make_terminal_call(spec_fn: str, raw_args: str, idx: str, arr_len: str) -> str:
    """
    Replace the loop-counter argument `idx as int` with `arr_len` in the
    argument list to get the post-loop value.
    """
    terminal_args = re.sub(
        rf"\b{re.escape(idx)}\s+as\s+int\b",
        arr_len,
        raw_args,
    )
    return f"{spec_fn}({terminal_args})"


def _find_arr_len_expr(code: str, idx: str) -> str:
    """
    Heuristic: find what `idx` iterates over (for <idx> in 0..<arr>.len())
    and return `<arr>@.len() as int` for use in the terminal assertion.
    Falls back to `<idx> as int` (identity) if not found.
    """
    m = re.search(
        rf"\bfor\s+{re.escape(idx)}\s+in\s+0\.\.(\w+)\.len\(\)", code
    )
    if m:
        return f"{m.group(1)}@.len() as int"
    return f"{idx} as int"


class PostconditionStrategy(Strategy):
    name = "postcond"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []

        info = _extract_bridge_info(code)
        if info is None:
            return cands
        acc, spec_fn, raw_args, idx = info

        # Don't add a proof block if one is already present.
        if "proof {" in code:
            return cands

        arr_len = _find_arr_len_expr(code, idx)
        terminal_call = _make_terminal_call(spec_fn, raw_args, idx, arr_len)
        assert_stmt = (
            f"    proof {{\n"
            f"        assert({acc} as int == {terminal_call});\n"
            f"    }}\n"
        )

        # Insert the proof block before `    <acc>\n}` (bare return value).
        bare_return = f"    {acc}\n}}"
        if bare_return in code:
            patched = code.replace(
                bare_return, assert_stmt + bare_return, 1
            )
            if patched != code:
                cands.append(
                    Candidate(
                        name=f"postcond-exit-bridge-{spec_fn}",
                        code=patched,
                        strategy=self.name,
                    )
                )
            return cands

        # Also try  `return <acc>;`  form.
        return_stmt = re.search(rf"\breturn\s+{re.escape(acc)}\s*;", code)
        if return_stmt:
            patched = (
                code[: return_stmt.start()]
                + assert_stmt
                + code[return_stmt.start() :]
            )
            cands.append(
                Candidate(
                    name=f"postcond-exit-bridge-{spec_fn}",
                    code=patched,
                    strategy=self.name,
                )
            )

        return cands
