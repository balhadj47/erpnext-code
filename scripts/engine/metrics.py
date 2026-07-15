"""Phase 11.2: Metrics Instrumentation

Records per-phase timings and build-level statistics.
Uses context managers for clean instrumentation.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class Timing:
    name: str
    start_ms: float = 0.0
    end_ms: float = 0.0
    duration_ms: int = 0

    def elapsed(self) -> int:
        return int((self.end_ms - self.start_ms) * 1000) if self.end_ms else 0


@dataclass
class BuildMetrics:
    """Complete metrics for a single build."""

    # Timing
    planning_time_ms: int = 0
    generation_time_ms: int = 0
    validation_time_ms: int = 0
    bench_time_ms: int = 0
    browser_time_ms: int = 0
    total_time_ms: int = 0

    # Counts
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_blocked: int = 0
    tasks_skipped: int = 0
    repair_count: int = 0
    retry_count: int = 0
    generated_files: int = 0
    modified_files: int = 0
    critical_issues: int = 0
    warnings: int = 0

    # Rates
    success_rate: float = 0.0

    # Phases
    phases: list[Timing] = field(default_factory=list)

    def compute_rates(self):
        if self.tasks_total > 0:
            self.success_rate = (self.tasks_completed / self.tasks_total) * 100

    def add_phase(self, name: str, duration_ms: int):
        self.phases.append(Timing(name=name, duration_ms=duration_ms))

    def to_dict(self) -> dict:
        self.compute_rates()
        return {
            "planning_time_ms": self.planning_time_ms,
            "generation_time_ms": self.generation_time_ms,
            "validation_time_ms": self.validation_time_ms,
            "bench_time_ms": self.bench_time_ms,
            "browser_time_ms": self.browser_time_ms,
            "total_time_ms": self.total_time_ms,
            "tasks_total": self.tasks_total,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_blocked": self.tasks_blocked,
            "tasks_skipped": self.tasks_skipped,
            "repair_count": self.repair_count,
            "retry_count": self.retry_count,
            "generated_files": self.generated_files,
            "modified_files": self.modified_files,
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "success_rate": round(self.success_rate, 1),
            "phases": [{"name": p.name, "duration_ms": p.duration_ms} for p in self.phases],
        }


class MetricsCollector:
    """Collects timing and count metrics during a build."""

    def __init__(self):
        self.metrics = BuildMetrics()
        self._start = time.time()
        self._timers: dict[str, float] = {}

    @contextmanager
    def phase(self, name: str):
        """Context manager to time a phase."""
        t0 = time.time()
        try:
            yield
        finally:
            elapsed = int((time.time() - t0) * 1000)
            self.metrics.add_phase(name, elapsed)
            # Map phase names to metric fields
            field_map = {
                "planning": "planning_time_ms",
                "generation": "generation_time_ms",
                "validation": "validation_time_ms",
                "bench": "bench_time_ms",
                "browser": "browser_time_ms",
            }
            for key, field in field_map.items():
                if key in name.lower():
                    setattr(self.metrics, field, elapsed)

    def start_phase(self, name: str):
        self._timers[name] = time.time()

    def end_phase(self, name: str):
        if name in self._timers:
            elapsed = int((time.time() - self._timers[name]) * 1000)
            self.metrics.add_phase(name, elapsed)
            del self._timers[name]

    def finish(self):
        self.metrics.total_time_ms = int((time.time() - self._start) * 1000)
        self.metrics.compute_rates()
        return self.metrics
