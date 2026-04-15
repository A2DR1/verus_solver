import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-json", required=True)
    args = parser.parse_args()

    rows = json.loads(Path(args.bench_json).read_text())
    solver_success = sum(1 for r in rows if r["solved_success"])
    av_success = sum(1 for r in rows if r.get("autoverus_status") == "success")
    out = {
        "total": len(rows),
        "solver_success": solver_success,
        "autoverus_success_from_logs": av_success,
        "solver_minus_autoverus": solver_success - av_success,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

