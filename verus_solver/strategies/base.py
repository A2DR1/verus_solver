from abc import ABC, abstractmethod
from typing import List

from ..models import Candidate, VerusResult

OPT_IN_PREFIX = "// verus_solver:strategy="


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        raise NotImplementedError


class RecipeStrategy(Strategy, ABC):
    """A high-recall, low-generalization template strategy.

    Recipe strategies replace whole function bodies with canned proofs.
    They are powerful for the exact benchmark shapes they target but risk
    overwriting intent in unrelated code.  They are therefore **opt-in**:

    * Set ``enable_recipes=True`` in ``SolverConfig`` to enable globally, OR
    * Add a per-file comment ``// verus_solver:strategy=<name>`` to opt in
      only for that file.

    Without opt-in they silently skip, letting generic tactics run instead.
    """

    def __init__(self, enable_recipes: bool = False) -> None:
        self._enable_recipes = enable_recipes

    def _is_opted_in(self, code: str) -> bool:
        return self._enable_recipes or f"{OPT_IN_PREFIX}{self.name}" in code

