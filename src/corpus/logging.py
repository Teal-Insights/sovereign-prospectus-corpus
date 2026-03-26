"""Structured JSONL logging for pipeline telemetry."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator


class CorpusLogger:
    """Append-only JSONL logger with run_id context."""

    _RESERVED_KEYS = frozenset(
        {"timestamp", "run_id", "document_id", "step", "duration_ms", "status", "error_message"}
    )

    def __init__(self, log_file: str | Path, *, run_id: str) -> None:
        self.log_file = Path(log_file)
        self.run_id = run_id
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        document_id: str,
        step: str,
        duration_ms: int,
        status: str,
        **extra: Any,
    ) -> None:
        """Append one structured log entry."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            "document_id": document_id,
            "step": step,
            "duration_ms": duration_ms,
            "status": status,
            **extra,
        }
        with self.log_file.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    @contextmanager
    def timed(self, document_id: str, step: str, **extra: Any) -> Generator[None, None, None]:
        """Context manager that logs duration and status automatically."""
        # Strip reserved keys from extras to avoid conflicts with log() kwargs
        safe_extra = {k: v for k, v in extra.items() if k not in self._RESERVED_KEYS}
        start = time.monotonic()
        try:
            yield
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self.log(
                document_id=document_id,
                step=step,
                duration_ms=elapsed_ms,
                status="success",
                **safe_extra,
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self.log(
                document_id=document_id,
                step=step,
                duration_ms=elapsed_ms,
                status="error",
                error_message=str(exc),
                **safe_extra,
            )
            raise
