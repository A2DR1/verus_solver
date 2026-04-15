# Verifier-Guided Verus Solver

Standalone CLI that improves Verus proof success via:

- verifier-first error triage
- deterministic repair strategies
- adaptive strategy switching when failures repeat
- iterative candidate search with checkpoints
- optional LLM fallback

## Quick start

```bash
python -m verus_solver.cli solve path/to/input.rs --out path/to/output.rs --config verus_solver/config.example.yaml
```

## Commands

- `solve`: run solver loop
- `resume`: continue from a checkpoint directory
- `explain`: print latest run summary
- `bench`: run on a folder of tasks

## Config

Copy `verus_solver/config.local.example.yaml` and set:

- `verus_path`: absolute path to Verus binary
- `repair_budget`: iteration budget
- `max_candidates_per_step`: beam width
- `strategy_order`: priority list
- `use_llm_fallback`: optional model fallback

## Output artifacts

Each run writes:

- `attempts/attempt_XXX.rs` and metadata
- `best_candidate.rs`
- `best_result.json`
- `summary.json`

## Benchmark + comparison

```bash
python -m verus_solver.bench.run_bench --tasks-dir my_inputs --config verus_solver/config.local.example.yaml --out-dir verus_solver_bench
python -m verus_solver.bench.compare_report --bench-json verus_solver_bench/bench_results.json
```

Optional: if you place AutoVerus run logs under `my_inputs/_run_logs/` (e.g. `autoverus_*.txt`), the bench harness can compare against them (`autoverus_status` in reports).

