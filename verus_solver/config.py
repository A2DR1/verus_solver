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
        default_factory=lambda: ["slice_precond", "invariant", "overflow", "postcond", "type_repair"]
    )
    use_llm_fallback: bool = False
    model: str = "gpt-4o"
    temperature: float = 0.2
    artifacts_root: str = "verus_solver_runs"
    multiple_errors: int = 3
    api_base: Optional[str] = None

    @staticmethod
    def from_file(path: str) -> "SolverConfig":
        data = yaml.safe_load(Path(path).read_text()) or {}
        return SolverConfig(**data)

