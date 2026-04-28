"""
InvariantStrategy: inject loop invariants for for-loops that accumulate a value.

General pattern detected:
  1. A for-loop  `for <idx> in 0..<arr>.len() {`  with no invariant block yet.
  2. An accumulator declared before the loop:  `let mut <acc>: <ty> = 0;`
  3. Optionally, a spec function referenced in the function's `ensures` clause
     with a terminal argument `<arr>@.len() as int` — we swap that for
     `<idx> as int` to form the loop invariant.

If a spec function can be inferred the emitted invariant is:
    invariant
        0 <= <idx> <= <arr>.len(),
        <acc> as int == <spec_fn>(<inferred-args-with-idx>),

Otherwise (no spec fn found) only the bounds invariant is emitted — that is
still useful for the verifier to track progress.
"""
import re
from typing import List, Optional

from ..models import Candidate, VerusResult
from .base import Strategy

# for <idx> in 0..<arr>.len() {   (no invariant/decreases immediately follows)
_FOR_LOOP_RE = re.compile(
    r"(?m)([ \t]*)for\s+(\w+)\s+in\s+0\.\.(\w+)\.len\(\)\s*\{"
)
# let mut <acc>: <ty> = 0;
_ACCUM_RE = re.compile(r"let\s+mut\s+(\w+)\s*:\s*\w+\s*=\s*0\s*;")
# spec fn <name>(
_SPEC_FN_RE = re.compile(r"\bspec\s+fn\s+(\w+)\b")
# ensures ... <spec_fn>(<args>)
_ENSURES_CALL_RE = re.compile(
    r"ensures\b[^{;]*?(\w+)\(([^;{]+)\)", re.DOTALL
)


def _loop_already_annotated(code: str, loop_start: int) -> bool:
    """Return True if the character after `{` already opens an invariant/decreases block."""
    # Look at what comes between the loop header and the body.
    snippet = code[loop_start : loop_start + 200]
    # The regex matched up to the `{`; what's inside?
    inner = re.search(r"\{(.*)", snippet, re.DOTALL)
    if inner:
        after = inner.group(1).lstrip()
        if after.startswith("invariant") or after.startswith("decreases"):
            return True
    return False


def _infer_spec_invariant(
    code: str, arr: str, idx: str, acc: str
) -> Optional[str]:
    """
    Look at the ensures clause for a spec fn call whose last int argument is
    `<arr>@.len() as int` and substitute `<idx> as int` to get a loop invariant.
    Returns None if no suitable call is found.
    """
    spec_fns = _SPEC_FN_RE.findall(code)
    if not spec_fns:
        return None

    for spec_fn in spec_fns:
        m = re.search(
            rf"\b{re.escape(spec_fn)}\s*\(([^;{{]+)\)", code, re.DOTALL
        )
        if not m:
            continue
        raw_args = m.group(1)
        # Replace  <arr>@.len() as int  (or  <arr>.len() as int)  with  <idx> as int.
        subbed = re.sub(
            rf"\b{re.escape(arr)}@?\.len\(\)\s+as\s+int\b",
            f"{idx} as int",
            raw_args,
        )
        if subbed == raw_args:
            continue  # couldn't find the terminal argument to replace
        # Normalise whitespace in the argument list.
        subbed = re.sub(r"\s+", " ", subbed).strip()
        return f"{acc} as int == {spec_fn}({subbed})"
    return None


def _second_array(code: str, arr: str, loop_start: int, loop_end: int) -> Optional[str]:
    """
    Find a second slice parameter used inside the loop body (common in pairwise
    computations like dot-product).  Returns its name or None.
    """
    body = code[loop_start:loop_end]
    # Look for  <name>.len()  where name != arr
    for m in re.finditer(r"\b(\w+)\.len\(\)", body):
        name = m.group(1)
        if name != arr:
            return name
    return None


class InvariantStrategy(Strategy):
    name = "invariant"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []

        accum_match = _ACCUM_RE.search(code)
        if accum_match is None:
            return cands  # no accumulator → nothing to annotate

        acc = accum_match.group(1)

        for m in _FOR_LOOP_RE.finditer(code):
            indent, idx, arr = m.group(1), m.group(2), m.group(3)
            loop_brace_pos = m.end() - 1  # position of the `{`

            if _loop_already_annotated(code, loop_brace_pos):
                continue  # already has invariant/decreases

            # Find end of loop body (matching `}`).
            depth = 0
            j = loop_brace_pos
            while j < len(code):
                if code[j] == "{":
                    depth += 1
                elif code[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            loop_end = j

            inner_indent = indent + "    "
            inv_lines: list[str] = [
                f"{inner_indent}invariant",
                f"{inner_indent}    0 <= {idx} <= {arr}.len(),",
            ]

            # Equality constraint with a second array if present.
            arr2 = _second_array(code, arr, m.start(), loop_end)
            if arr2:
                inv_lines.append(f"{inner_indent}    {arr}.len() == {arr2}.len(),")

            # Spec function invariant if we can infer one.
            spec_inv = _infer_spec_invariant(code, arr, idx, acc)
            if spec_inv:
                inv_lines.append(f"{inner_indent}    {spec_inv},")

            inv_block = "\n".join(inv_lines) + "\n"
            # Insert invariant block between the loop header `{` and the body.
            # The for-loop match ends at the character after `{`, so we splice there.
            header_end = m.end()  # index just past `{`
            patched = code[:header_end] + "\n" + inv_block + code[header_end:]

            tag = f"invariant-{arr}-{idx}-{acc}"
            if spec_inv:
                tag += "-spec"
            cands.append(Candidate(name=tag, code=patched, strategy=self.name))
            break  # one candidate per call; solver evaluates and picks the best

        return cands
