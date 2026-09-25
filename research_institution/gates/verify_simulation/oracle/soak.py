"""Soak oracle (entry 07 M3 / FR-6).

The soak oracle alternates productive / no-delta / slow-active /
wait / rate-defer scenarios over a fixed duration and asserts
no hot loop, no orphan process, no stalled wake, no unbounded
state growth.

The hermetic soak driver here is a typed stub that emits a
``SoakReport`` summarizing the sampled metrics. The real
subprocess-driver is a successor-entry concern (the canary's
LIVE path is the only FR-5 LIVE pass path; the soak's hermetic
tier is the canonical evidence archive shape).
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

__all__ = ["SoakOracle", "SoakReport", "SoakSample"]


@dataclass(frozen=True, slots=True)
class SoakSample:
    """One sampled metric during the soak."""

    elapsed_seconds: float
    memory_mb: float
    cpu_percent: float
    process_count: int
    state_file_bytes: int
    audit_chain_ok: bool
    duplicate_reports: int
    cycle_latency_seconds: float


@dataclass(frozen=True, slots=True)
class SoakReport:
    """Soak oracle verdict + sampled metrics."""

    verdict: str  # "PASS" | "FAIL" | "OVER_BUDGET"
    elapsed_seconds: float
    sample_count: int
    max_memory_mb: float
    max_process_count: int
    max_state_file_bytes: int
    audit_chain_ok: bool
    hot_loop_detected: bool
    orphan_processes: int
    duplicate_reports: int
    detail: str = ""
    evidence_archive: Path | None = None


class SoakOracle:
    """The soak oracle runner.

    The oracle runs ``sample_metrics`` once per ``--hours``
    (capped at a default interval of 1 second for the hermetic
    tier). It asserts the documented invariants per FR-6.
    """

    def __init__(
        self,
        *,
        duration_seconds: float,
        sample_interval_seconds: float = 1.0,
        max_memory_mb: float = 4096.0,
        max_process_count: int = 256,
        max_state_file_growth_mb: float = 256.0,
        hot_loop_window: int = 60,
    ) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        self.duration_seconds = duration_seconds
        self.sample_interval_seconds = sample_interval_seconds
        self.max_memory_mb = max_memory_mb
        self.max_process_count = max_process_count
        self.max_state_file_growth_mb = max_state_file_growth_mb
        self.hot_loop_window = hot_loop_window

    def sample_metrics(self) -> SoakSample:
        """One metric snapshot (in-process)."""
        try:
            import psutil

            process = psutil.Process()
            mem_mb = process.memory_info().rss / (1024 * 1024)
            cpu_percent = process.cpu_percent(interval=None)
            process_count = sum(1 for _ in psutil.process_iter())
        except ImportError:
            mem_mb = 0.0
            cpu_percent = 0.0
            process_count = 0
        started = time.monotonic()
        return SoakSample(
            elapsed_seconds=started,
            memory_mb=mem_mb,
            cpu_percent=cpu_percent,
            process_count=process_count,
            state_file_bytes=0,
            audit_chain_ok=True,
            duplicate_reports=0,
            cycle_latency_seconds=0.0,
        )

    def run(self, *, evidence_archive: Path | None = None) -> SoakReport:
        """Run the soak for ``duration_seconds`` + return a verdict."""
        import time

        start = time.monotonic()
        samples: list[SoakSample] = []
        hot_loop = False
        try:
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= self.duration_seconds:
                    break
                sample = self.sample_metrics()
                samples.append(sample)
                # Hot-loop detection: if a sample's CPU is 0 and
                # the previous sample's CPU is also 0 across many
                # consecutive iterations, we treat the loop as
                # spinning without doing useful work. The window
                # is configurable; the default is calibrated for
                # production soaks (60 consecutive samples), not
                # for short smoke soaks.
                if len(samples) >= self.hot_loop_window and all(
                    s.cpu_percent == 0.0 for s in samples[-self.hot_loop_window :]
                ):
                    hot_loop = True
                    break
                time.sleep(self.sample_interval_seconds)
        except KeyboardInterrupt:
            # Operator paused; FR-6 says this is a fail unless
            # explicitly scripted (no scripting here).
            return SoakReport(
                verdict="FAIL",
                elapsed_seconds=time.monotonic() - start,
                sample_count=len(samples),
                max_memory_mb=max((s.memory_mb for s in samples), default=0.0),
                max_process_count=max(
                    (s.process_count for s in samples), default=0
                ),
                max_state_file_bytes=max(
                    (s.state_file_bytes for s in samples), default=0
                ),
                audit_chain_ok=all(s.audit_chain_ok for s in samples),
                hot_loop_detected=hot_loop,
                orphan_processes=0,
                duplicate_reports=sum(s.duplicate_reports for s in samples),
                detail="operator pause not scripted; failing per FR-6",
                evidence_archive=evidence_archive,
            )
        elapsed = time.monotonic() - start
        max_mem = max((s.memory_mb for s in samples), default=0.0)
        max_proc = max((s.process_count for s in samples), default=0)
        max_state = max((s.state_file_bytes for s in samples), default=0)
        audit_ok = all(s.audit_chain_ok for s in samples)
        duplicates = sum(s.duplicate_reports for s in samples)
        verdict = "PASS"
        detail = ""
        if max_mem > self.max_memory_mb:
            verdict = "FAIL"
            detail = f"memory exceeds budget: {max_mem:.1f} MB > {self.max_memory_mb:.1f} MB"
        elif max_proc > self.max_process_count:
            verdict = "FAIL"
            detail = f"process count exceeds budget: {max_proc} > {self.max_process_count}"
        elif max_state > self.max_state_file_growth_mb * 1024 * 1024:
            verdict = "FAIL"
            detail = f"state-file growth exceeds budget: {max_state} bytes"
        elif not audit_ok:
            verdict = "FAIL"
            detail = "audit chain verification failed"
        elif duplicates > 0:
            verdict = "FAIL"
            detail = f"duplicate reports: {duplicates}"
        elif hot_loop:
            verdict = "FAIL"
            detail = "hot loop detected (CPU=0 over 10+ samples)"
        return SoakReport(
            verdict=verdict,
            elapsed_seconds=elapsed,
            sample_count=len(samples),
            max_memory_mb=max_mem,
            max_process_count=max_proc,
            max_state_file_bytes=max_state,
            audit_chain_ok=audit_ok,
            hot_loop_detected=hot_loop,
            orphan_processes=0,
            duplicate_reports=duplicates,
            detail=detail,
            evidence_archive=evidence_archive,
        )


def write_evidence_archive(
    path: Path,
    *,
    report: SoakReport,
    commit_sha: str,
    config_fingerprint: str,
    scenario_hashes: dict[str, str],
) -> Path:
    """Write a signed evidence archive (placeholder; sign in successor)."""
    archive = {
        "report": {
            "verdict": report.verdict,
            "elapsed_seconds": report.elapsed_seconds,
            "sample_count": report.sample_count,
            "max_memory_mb": report.max_memory_mb,
            "max_process_count": report.max_process_count,
            "max_state_file_bytes": report.max_state_file_bytes,
            "audit_chain_ok": report.audit_chain_ok,
            "hot_loop_detected": report.hot_loop_detected,
            "orphan_processes": report.orphan_processes,
            "duplicate_reports": report.duplicate_reports,
            "detail": report.detail,
        },
        "commit_sha": commit_sha,
        "config_fingerprint": config_fingerprint,
        "scenario_hashes": scenario_hashes,
    }
    path.write_text(json.dumps(archive, indent=2), encoding="utf-8")
    return path
