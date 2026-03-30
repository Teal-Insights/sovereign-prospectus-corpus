# scripts/pre_commit_private_check.py
"""Pre-commit hook: block commits containing private framing content.

Scans staged files for patterns that belong in docs/private/ (gitignored),
not in public tracked files.
"""

from __future__ import annotations

import subprocess
import sys

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


def get_staged_content() -> str:
    """Get the diff of all staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    diff = get_staged_content()
    lower_diff = diff.lower()

    violations = []
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in lower_diff:
            violations.append(pattern)

    if violations:
        print("BLOCKED: Staged files contain private content patterns:")
        for v in violations:
            print(f"  - {v!r}")
        print("\nThese patterns belong in docs/private/ (gitignored).")
        print("Remove them from tracked files before committing.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
