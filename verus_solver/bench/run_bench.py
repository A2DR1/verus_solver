import argparse
import csv
import json
from pathlib import Path
from time import perf_counter

from verus_solver.config import SolverConfig
from verus_solver.solver import VerifierGuidedSolver
from verus_solver.verus_runner import VerusRunner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-dir", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out-dir", default="verus_solver_bench")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = SolverConfig.from_file(args.config)
    solver = VerifierGuidedSolver(cfg)
    runner = VerusRunner(cfg.verus_path, multiple_errors=cfg.multiple_errors)

    rows = []
    autoverus_logs = Path(args.tasks_dir) / "_run_logs"
    for task in sorted(Path(args.tasks_dir).glob("*.rs")):
        baseline = runner.run_file(str(task))
        solved_out = out_dir / f"{task.stem}_solved.rs"
        t0 = perf_counter()
        solved = solver.solve(str(task), str(solved_out))
        elapsed = perf_counter() - t0
        av_status = "unknown"
        av_log = autoverus_logs / f"autoverus_{task.stem.replace('_mannual', '')}.txt"
        if av_log.exists():
            text = av_log.read_text()
            if "Verus succeeded" in text:
                av_status = "success"
            else:
                av_status = "failed"
        rows.append(
            {
                "task": task.name,
                "baseline_verified": baseline.verified,
                "baseline_errors": baseline.errors,
                "solved_success": solved.success,
                "solved_verified": solved.verified,
                "solved_errors": solved.errors,
                "autoverus_status": av_status,
                "attempts": solved.attempts,
                "elapsed_sec": round(elapsed, 3),
                "run_dir": solved.run_dir,
            }
        )
        print(json.dumps(rows[-1], indent=2))

    csv_path = out_dir / "bench_results.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    (out_dir / "bench_results.json").write_text(json.dumps(rows, indent=2))
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()

