from .models import VerusResult


def score_result(result: VerusResult) -> int:
    # Higher is better.
    compile_penalty = 10_000 if result.compile_error else 0
    return (result.verified * 100) - (result.errors * 150) - compile_penalty

