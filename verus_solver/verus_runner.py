import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .error_parser import parse_issues
from .models import VerusResult


class VerusRunner:
    def __init__(self, verus_path: str, multiple_errors: int = 3):
        self.verus_path = verus_path
        self.multiple_errors = multiple_errors

    def run_code(self, code: str, verify_function: Optional[str] = None) -> VerusResult:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".rs", delete=False) as tf:
            tf.write(code)
            temp_file = tf.name
        return self.run_file(temp_file, verify_function=verify_function)

    def run_file(self, file_path: str, verify_function: Optional[str] = None) -> VerusResult:
        cmd = [self.verus_path, "--multiple-errors", str(self.multiple_errors), file_path]
        if verify_function:
            cmd.extend(["--verify-function", verify_function, "--verify-root"])

        proc = subprocess.run(cmd, text=True, capture_output=True)
        stdout, stderr = proc.stdout, proc.stderr
        verified, errors = extract_score(stdout)
        issues = parse_issues(stderr)
        compile_error = "aborting due to" in stderr.lower() and verified == 0 and errors == 0
        success = proc.returncode == 0 and errors == 0
        return VerusResult(
            success=success,
            verified=verified,
            errors=errors,
            compile_error=compile_error,
            raw_stdout=stdout,
            raw_stderr=stderr,
            issues=issues,
        )


def extract_score(stdout: str) -> tuple[int, int]:
    m = re.search(r"verification results::\s*(\d+)\s+verified,\s*(\d+)\s+errors", stdout)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))

