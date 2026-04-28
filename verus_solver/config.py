from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class SolverConfig:
    verus_path: str
    repair_budget: int = 12
    max_candidates_per_step: int = 4
    strategy_order: List[str] = field(
        default_factory=lambda: [
            # Compile-error recovery comes first so proof strategies
            # never waste iterations on code that doesn't even parse.
            "compile_error",
            "syntax_repair",
            # Generic structural tactics (variable-name agnostic).
            "decreases",
            "slice_precond",
            "structural_loop_inv",
            "overflow",
            "type_repair",
            # Proof-obligation tactics.
            "invariant",
            "postcond",
            # Reverse-function tactics (narrow but non-destructive).
            "reverse_swap",
            "reverse_semantic",
            "reverse_step_lemma",
        ]
    )
    use_llm_fallback: bool = False
    llm_stagnation_rounds: int = 1   # rounds without improvement before LLM fires
    enable_recipes: bool = False      # opt-in for full-template recipe strategies
    model: str = "gpt-4o"
    temperature: float = 0.2
    artifacts_root: str = "verus_solver_runs"
    multiple_errors: int = 3
    api_base: Optional[str] = None

    @staticmethod
    def from_file(path: str) -> "SolverConfig":
        data = yaml.safe_load(Path(path).read_text()) or {}
        return SolverConfig(**data)
