from typing import List, Optional, Tuple

from ..models import Candidate, VerusResult
from .base import Strategy


REVERSE_TEMPLATE = """
pub fn reverse(a: &mut [i32])
    requires
        old(a)@.len() >= 1,
    ensures
        a@.len() == old(a)@.len(),
        forall|k: int| 0 <= k && k < a@.len() ==> a@[k] == old(a)@[a@.len() - 1 - k],
{
    if a.len() == 0 { return; }
    let n = a.len();
    let mut lo = 0usize;
    let mut hi = n - 1;
    while lo < hi
        invariant
            n == a.len(),
            n == old(a)@.len(),
            0 <= lo <= n,
            0 <= hi < n,
            lo + hi + 1 == n,
            lo <= hi + 1,
            (lo as int) <= (n as int) - (lo as int),
            forall|k: int| 0 <= k && k < (lo as int) ==> a@[k] == old(a)@[n as int - 1 - k],
            forall|k: int| (n as int) - (lo as int) <= k && k < (n as int) ==> a@[k] == old(a)@[n as int - 1 - k],
            forall|k: int| (lo as int) <= k && k < (n as int) - (lo as int) ==> a@[k] == old(a)@[k],
        decreases n - lo,
    {
        let tmp = a[lo];
        a[lo] = a[hi];
        a[hi] = tmp;
        lo += 1;
        hi -= 1;
    }
}
""".strip()


class ReverseTemplateStrategy(Strategy):
    name = "reverse_template"

    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        cands: List[Candidate] = []
        if "pub fn reverse(" not in code:
            return cands
        block = _extract_reverse_function_block(code)
        if block is None:
            return cands
        start, end = block
        patched = code[:start] + REVERSE_TEMPLATE + code[end:]
        cands.append(Candidate(name="reverse-complete-template", code=patched, strategy=self.name))
        return cands


def _extract_reverse_function_block(code: str) -> Optional[Tuple[int, int]]:
    start = code.find("pub fn reverse(")
    if start == -1:
        return None
    brace_open = code.find("{", start)
    if brace_open == -1:
        return None
    depth = 0
    i = brace_open
    while i < len(code):
        ch = code[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return (start, i + 1)
        i += 1
    return None

