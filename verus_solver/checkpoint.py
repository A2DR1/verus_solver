import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .models import Candidate, ScoredCandidate


class CheckpointStore:
    def __init__(self, run_dir: str):
        self.run_dir = Path(run_dir)
        self.attempts = self.run_dir / "attempts"
        self.attempts.mkdir(parents=True, exist_ok=True)

    def save_attempt(self, idx: int, scored: ScoredCandidate) -> None:
        code_path = self.attempts / f"attempt_{idx:03d}.rs"
        meta_path = self.attempts / f"attempt_{idx:03d}.json"
        code_path.write_text(scored.candidate.code)
        meta = {
            "name": scored.candidate.name,
            "strategy": scored.candidate.strategy,
            "score": scored.score,
            "verified": scored.result.verified,
            "errors": scored.result.errors,
            "success": scored.result.success,
            "compile_error": scored.result.compile_error,
            "notes": scored.candidate.notes,
        }
        meta_path.write_text(json.dumps(meta, indent=2))

    def save_best(self, scored: ScoredCandidate) -> None:
        (self.run_dir / "best_candidate.rs").write_text(scored.candidate.code)
        (self.run_dir / "best_result.json").write_text(
            json.dumps(
                {
                    "name": scored.candidate.name,
                    "strategy": scored.candidate.strategy,
                    "score": scored.score,
                    "verified": scored.result.verified,
                    "errors": scored.result.errors,
                    "success": scored.result.success,
                },
                indent=2,
            )
        )

    def save_summary(self, summary: dict) -> None:
        (self.run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    @staticmethod
    def latest_run(root_dir: str) -> Optional[str]:
        root = Path(root_dir)
        if not root.exists():
            return None
        runs = [p for p in root.iterdir() if p.is_dir()]
        if not runs:
            return None
        runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return str(runs[0])

