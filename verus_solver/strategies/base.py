from abc import ABC, abstractmethod
from typing import List

from ..models import Candidate, VerusResult


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, code: str, result: VerusResult) -> List[Candidate]:
        raise NotImplementedError

