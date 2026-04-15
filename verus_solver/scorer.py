from typing import Optional

from .models import VerusResult


def score_result(result: VerusResult, prev: Optional[VerusResult] = None) -> int:
    """Score a verification result.  Higher is better.

    Base score
    ----------
    * +100 per verified item
    * -150 per error
    * -10 000 if the code did not compile at all

    Progress bonus (only when *prev* is supplied)
    ----------------------------------------------
    * +40 for every *error kind* that was present in *prev* but is gone now.
      This rewards candidates that eliminated a whole class of obligation even
      if the total error count didn't change (e.g. fixed overflow but introduced
      a new invariant failure with the same count).
    * +20 for each individual error line number that disappeared.
      This rewards narrowing the problem even within the same kind.
    """
    compile_penalty = 10_000 if result.compile_error else 0
    base = result.verified * 100 - result.errors * 150 - compile_penalty

    if prev is not None:
        prev_kinds = {i.kind for i in prev.issues}
        cur_kinds = {i.kind for i in result.issues}
        eliminated_kinds = prev_kinds - cur_kinds
        base += len(eliminated_kinds) * 40

        prev_lines = {(i.kind, i.line) for i in prev.issues}
        cur_lines = {(i.kind, i.line) for i in result.issues}
        eliminated_lines = prev_lines - cur_lines
        base += len(eliminated_lines) * 20

    return base
