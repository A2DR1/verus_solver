import re
from typing import List

from .models import VerusIssue


def parse_issues(stderr: str) -> List[VerusIssue]:
    issues: List[VerusIssue] = []
    lines = stderr.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("error"):
            msg = line
            file_name = None
            line_no = None
            # Try to read rust-style location lines near the current point.
            for j in range(i + 1, min(i + 8, len(lines))):
                loc = re.search(r"--> (.+):(\d+):\d+", lines[j])
                if loc:
                    file_name = loc.group(1)
                    line_no = int(loc.group(2))
                    break
            issues.append(VerusIssue(kind=classify_issue(msg, stderr), message=msg, file=file_name, line=line_no))
        i += 1
    return issues


def classify_issue(message: str, stderr: str) -> str:
    lower = message.lower()
    whole = stderr.lower()
    if "postcondition not satisfied" in lower:
        return "postcond"
    if "precondition not satisfied" in lower:
        return "slice_precond"
    if "underflow/overflow" in lower or "arithmetic overflow" in whole:
        return "overflow"
    if "invariant" in lower or "while loop" in whole:
        return "invariant"
    if "mismatched types" in lower:
        return "type_repair"
    if "decreases clause" in lower:
        return "decreases"
    return "other"

