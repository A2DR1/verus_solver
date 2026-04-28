from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .checkpoint import CheckpointStore
from .config import SolverConfig
from .llm_fallback import LLMFallback
from .models import Candidate, ScoredCandidate, VerusResult
from .scorer import score_result
from .strategies import (
    DecreasesStrategy,
    InvariantStrategy,
    OverflowStrategy,
    PostconditionStrategy,
    SlicePrecondStrategy,
    Strategy,
    StructuralLoopInvariantStrategy,
    SyntaxRepairStrategy,
    TypeRepairStrategy,
)
from .triage import top_error_class
from .verus_runner import VerusRunner


@dataclass
class SolveResult:
    success: bool
    run_dir: str
    best_file: str
    verified: int
    errors: int
    attempts: int


@dataclass
class AdaptiveState:
    stagnation_rounds: int = 0
    last_signature: str = ""
    strategy_cursor: int = 0
    decisions: List[dict] = field(default_factory=list)


class VerifierGuidedSolver:
    def __init__(self, config: SolverConfig):
        self.config = config
        self.runner = VerusRunner(config.verus_path, multiple_errors=config.multiple_errors)
        self.strategies = self._build_strategies()
        self.llm = (
            LLMFallback(
                config.model,
                temperature=config.temperature,
                api_base=config.api_base,
                runner=self.runner,
            )
            if config.use_llm_fallback
            else None
        )

    def _build_strategies(self) -> Dict[str, Strategy]:
        strategy_list: List[Strategy] = [
            # Compile-error recovery — runs before any proof strategy.
            SyntaxRepairStrategy(),
            # Generic structural tactics (variable-name agnostic).
            DecreasesStrategy(),
            SlicePrecondStrategy(),
            StructuralLoopInvariantStrategy(),
            OverflowStrategy(),
            TypeRepairStrategy(),
            # Proof-obligation tactics.
            InvariantStrategy(),
            PostconditionStrategy(),
        ]
        return {s.name: s for s in strategy_list}

    # ------------------------------------------------------------------
    # Main solve loop
    # ------------------------------------------------------------------

    def solve(self, input_file: str, output_file: str) -> SolveResult:
        code = Path(input_file).read_text()
        run_dir = self._new_run_dir(Path(input_file).stem)
        store = CheckpointStore(str(run_dir))

        base = Candidate(name="baseline", code=code, strategy="baseline")
        base_result = self.runner.run_code(code)
        best = ScoredCandidate(base, base_result, score_result(base_result))
        store.save_attempt(0, best)
        store.save_best(best)

        if best.result.success:
            Path(output_file).write_text(best.candidate.code)
            summary = self._summary(best, attempts=1, run_dir=str(run_dir), decisions=[])
            store.save_summary(summary)
            return SolveResult(
                True, str(run_dir), str(run_dir / "best_candidate.rs"),
                best.result.verified, best.result.errors, 1,
            )

        attempt_idx = 1
        adaptive = AdaptiveState()

        for _step in range(self.config.repair_budget):
            err_class = top_error_class(best.result, self.config.strategy_order)
            signature = self._error_signature(best.result)

            if signature == adaptive.last_signature:
                adaptive.stagnation_rounds += 1
            else:
                adaptive.stagnation_rounds = 0
                adaptive.last_signature = signature

            candidate_pool: List[Candidate] = []
            used_strategies: List[str] = []

            # When the code doesn't compile, put syntax_repair first regardless
            # of the normal strategy order so we escape the compile-error basin
            # as quickly as possible.
            strategy_seq = self._adaptive_strategy_sequence(err_class, adaptive)
            if best.result.compile_error and "syntax_repair" not in strategy_seq:
                strategy_seq = ["syntax_repair"] + strategy_seq

            for strategy_name in strategy_seq:
                strategy = self.strategies.get(strategy_name)
                if not strategy:
                    continue
                generated = strategy.generate(best.candidate.code, best.result)
                if generated:
                    used_strategies.append(strategy_name)
                    candidate_pool.extend(generated)
                if len(candidate_pool) >= self.config.max_candidates_per_step:
                    break

            # LLM fast-paths:
            #   1. No deterministic candidates at all → try LLM immediately.
            #   2. Stagnating for llm_stagnation_rounds without improvement.
            #   3. Compile error that syntax_repair couldn't fix → LLM for
            #      creative fixes (it sees the raw stderr).
            stagnating = adaptive.stagnation_rounds >= self.config.llm_stagnation_rounds
            no_candidates = not candidate_pool
            compile_unfixed = best.result.compile_error and not candidate_pool
            use_llm_now = stagnating or no_candidates or compile_unfixed

            if use_llm_now and self.llm is not None:
                try:
                    llm_cands = self.llm.generate(
                        best.candidate.code,
                        best.result,
                        self.config.max_candidates_per_step,
                    )
                    if llm_cands:
                        used_strategies.append("llm_fallback")
                        if stagnating:
                            # When stagnating, put LLM candidates at the FRONT so
                            # the truncation below keeps them over the deterministic
                            # candidates that have already been tried.
                            candidate_pool = llm_cands + candidate_pool
                        else:
                            candidate_pool.extend(llm_cands)
                except Exception:
                    pass

            if not candidate_pool:
                adaptive.decisions.append({
                    "error_class": err_class,
                    "signature": signature,
                    "stagnation_rounds": adaptive.stagnation_rounds,
                    "used_strategies": used_strategies,
                    "result": "no_candidates",
                })
                break

            candidate_pool = candidate_pool[: self.config.max_candidates_per_step]
            improved = False

            for cand in candidate_pool:
                cand_result = self.runner.run_code(cand.code)
                # Pass the current best result as baseline so the richer scorer
                # can reward eliminating whole error kinds.
                cand_score = score_result(cand_result, prev=best.result)
                scored = ScoredCandidate(cand, cand_result, cand_score)
                store.save_attempt(attempt_idx, scored)
                attempt_idx += 1
                # Feed actual Verus outcome back to the LLM so the next round's
                # prompt reflects what really happened, not just what we hoped.
                if cand.strategy == "llm_fallback" and self.llm is not None:
                    self.llm.update_last_result(cand_result)

                if scored.score > best.score:
                    best = scored
                    store.save_best(best)
                    improved = True
                    if best.result.success:
                        Path(output_file).write_text(best.candidate.code)
                        adaptive.decisions.append({
                            "error_class": err_class,
                            "signature": signature,
                            "stagnation_rounds": adaptive.stagnation_rounds,
                            "used_strategies": used_strategies,
                            "result": "improved_and_success",
                        })
                        summary = self._summary(
                            best, attempts=attempt_idx,
                            run_dir=str(run_dir), decisions=adaptive.decisions,
                        )
                        store.save_summary(summary)
                        return SolveResult(
                            True, str(run_dir), str(run_dir / "best_candidate.rs"),
                            best.result.verified, best.result.errors, attempt_idx,
                        )

            if not improved:
                adaptive.decisions.append({
                    "error_class": err_class,
                    "signature": signature,
                    "stagnation_rounds": adaptive.stagnation_rounds,
                    "used_strategies": used_strategies,
                    "result": "no_improvement",
                })
                adaptive.strategy_cursor += 1
                continue

            adaptive.decisions.append({
                "error_class": err_class,
                "signature": signature,
                "stagnation_rounds": adaptive.stagnation_rounds,
                "used_strategies": used_strategies,
                "result": "improved",
            })

        Path(output_file).write_text(best.candidate.code)
        summary = self._summary(
            best, attempts=attempt_idx, run_dir=str(run_dir), decisions=adaptive.decisions,
        )
        store.save_summary(summary)
        return SolveResult(
            False, str(run_dir), str(run_dir / "best_candidate.rs"),
            best.result.verified, best.result.errors, attempt_idx,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _new_run_dir(self, stem: str) -> Path:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = Path(self.config.artifacts_root) / f"{ts}-{stem}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def _adaptive_strategy_sequence(self, err_class: str, adaptive: AdaptiveState) -> List[str]:
        order = [n for n in self.config.strategy_order if n in self.strategies]
        if not order:
            return []
        seq = [err_class] if err_class in order else []
        alternates = order[:]
        if adaptive.stagnation_rounds >= 1:
            start = adaptive.strategy_cursor % len(alternates)
            alternates = alternates[start:] + alternates[:start]
        for n in alternates:
            if n not in seq:
                seq.append(n)
        return seq

    @staticmethod
    def _error_signature(result: VerusResult) -> str:
        if result.compile_error:
            return f"compile_error:{result.raw_stderr[:120]}"
        if not result.issues:
            return f"{result.verified}:{result.errors}:none"
        top = result.issues[0]
        return f"{result.verified}:{result.errors}:{top.kind}:{top.line}"

    @staticmethod
    def _summary(best: ScoredCandidate, attempts: int, run_dir: str, decisions: List[dict]) -> dict:
        return {
            "success": best.result.success,
            "verified": best.result.verified,
            "errors": best.result.errors,
            "score": best.score,
            "best_name": best.candidate.name,
            "best_strategy": best.candidate.strategy,
            "attempts": attempts,
            "run_dir": run_dir,
            "decisions": decisions,
        }
