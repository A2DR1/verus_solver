from typing import List

from .models import VerusResult


def top_error_class(result: VerusResult, strategy_order: List[str]) -> str:
    issue_kinds = [i.kind for i in result.issues]
    for kind in strategy_order:
        if kind in issue_kinds:
            return kind
    if issue_kinds:
        return issue_kinds[0]
    return "other"

