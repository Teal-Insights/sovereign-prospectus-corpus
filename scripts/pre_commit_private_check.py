# scripts/pre_commit_private_check.py
"""Pre-commit hook: block commits containing private framing content.

Scans staged files (and the branch name) for patterns that belong in
docs/private/ (gitignored), not in public tracked files.

In addition to the public patterns below, extra patterns are loaded from
docs/private/blocklist.txt (gitignored; one pattern per line, # comments).
That file holds patterns that are themselves private, so the check stays
mechanical without publishing what it protects. Violations from the
private list are reported redacted.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Patterns that should only appear in gitignored files.
# Keep this list in sync with docs/private/roundtable-framing.md.
BLOCKED_PATTERNS: list[str] = [
    "roundtable-framing.md",
    "review-round-",
    "persona review",
    "Teal persona",
    "Georgetown Law persona",
    "MDI persona",
]

PRIVATE_BLOCKLIST = Path(__file__).resolve().parent.parent / "docs" / "private" / "blocklist.txt"


def load_private_patterns() -> list[str]:
    """Extra patterns from the gitignored private blocklist, if present."""
    try:
        lines = PRIVATE_BLOCKLIST.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def redact(pattern: str) -> str:
    """Show enough to identify the hit locally without echoing the pattern."""
    return f"{pattern[:2]}{'*' * max(len(pattern) - 2, 3)} (private blocklist)"


def get_staged_content() -> str:
    """Get the diff of all staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def get_branch_name() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    diff = get_staged_content()
    branch = get_branch_name()
    lower_diff = diff.lower()
    lower_branch = branch.lower()
    private_patterns = load_private_patterns()

    violations: list[str] = []
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in lower_diff or pattern.lower() in lower_branch:
            violations.append(repr(pattern))
    for pattern in private_patterns:
        if pattern.lower() in lower_diff or pattern.lower() in lower_branch:
            violations.append(redact(pattern))

    if violations:
        print("BLOCKED: Staged files or branch name contain private content patterns:")
        for v in violations:
            print(f"  - {v}")
        print("\nThese patterns belong in docs/private/ (gitignored).")
        print("Remove them from tracked files before committing.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
