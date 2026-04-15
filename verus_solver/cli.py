import argparse
import json
import subprocess
import sys
from pathlib import Path

from .checkpoint import CheckpointStore
from .config import SolverConfig
from .solver import VerifierGuidedSolver


def cmd_solve(args):
    cfg = SolverConfig.from_file(args.config)
    solver = VerifierGuidedSolver(cfg)
    result = solver.solve(args.input, args.out)
    print(json.dumps(result.__dict__, indent=2))


def cmd_resume(args):
    run_dir = args.run_dir
    summary_path = Path(run_dir) / "summary.json"
    if summary_path.exists():
        print(summary_path.read_text())
    else:
        print(f"No summary at {summary_path}")


def cmd_explain(args):
    latest = CheckpointStore.latest_run(args.artifacts_root)
    if not latest:
        print("No runs found.")
        return
    summary = Path(latest) / "summary.json"
    if summary.exists():
        print(summary.read_text())
    else:
        print(f"Run exists but summary missing: {latest}")


def build_parser():
    p = argparse.ArgumentParser(description="Verifier-guided Verus solver")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("solve", help="Solve one Verus file")
    s.add_argument("input")
    s.add_argument("--out", required=True)
    s.add_argument("--config", required=True)
    s.set_defaults(func=cmd_solve)

    r = sub.add_parser("resume", help="Show existing run summary")
    r.add_argument("run_dir")
    r.set_defaults(func=cmd_resume)

    e = sub.add_parser("explain", help="Explain latest run")
    e.add_argument("--artifacts-root", default="verus_solver_runs")
    e.set_defaults(func=cmd_explain)

    b = sub.add_parser("bench", help="Run benchmark harness")
    b.add_argument("--tasks-dir", required=True)
    b.add_argument("--config", required=True)
    b.add_argument("--out-dir", default="verus_solver_bench")
    b.set_defaults(
        func=lambda args: subprocess.run(
            [
                sys.executable,
                "-m",
                "verus_solver.bench.run_bench",
                "--tasks-dir",
                args.tasks_dir,
                "--config",
                args.config,
                "--out-dir",
                args.out_dir,
            ],
            check=True,
        )
    )

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

