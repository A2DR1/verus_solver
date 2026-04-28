from typing import List

from .models import VerusResult


def top_error_class(result: VerusResult, strategy_order: List[str]) -> str:
    """Return the highest-priority error kind present in *result*.

    ``compile_error`` is always surfaced first when the verifier could not
    even parse or type-check the code — it must be resolved before any proof
    strategies can make progress.
    """
    if result.compile_error:
        return "compile_error"

    issue_kinds = [i.kind for i in result.issues]
    for kind in strategy_order:
        if kind in issue_kinds:
            return kind
    if issue_kinds:
        return issue_kinds[0]
    return "other"
