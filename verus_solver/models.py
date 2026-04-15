from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class VerusIssue:
    kind: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None


@dataclass
class VerusResult:
    success: bool
    verified: int
    errors: int
    compile_error: bool
    raw_stdout: str
    raw_stderr: str
    issues: List[VerusIssue] = field(default_factory=list)


@dataclass
class Candidate:
    name: str
    code: str
    strategy: str
    notes: str = ""
    parent: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ScoredCandidate:
    candidate: Candidate
    result: VerusResult
    score: int

