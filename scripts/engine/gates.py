"""Phase 11.1: Quality Gates

A build is NOT successful unless ALL gates pass.
Gates are ordered — later gates depend on earlier ones.
If any gate fails, the pipeline stops and generates a report.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class GateStatus(Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Gate:
    name: str
    description: str
    phase: int  # execution order
    depends_on: list[str] = field(default_factory=list)
    status: GateStatus = GateStatus.PENDING
    detail: str = ""
    duration_ms: int = 0

    def __hash__(self):
        return hash(self.name)


class GateRunner:
    """Runs quality gates in order. Stops on first failure."""

    GATES: list[Gate] = [
        Gate("planner", "Task planner completed successfully", phase=1),
        Gate("dependency_graph", "Dependency graph is valid and acyclic", phase=2, depends_on=["planner"]),
        Gate("code_generation", "All code generation tasks produced output", phase=3, depends_on=["dependency_graph"]),
        Gate("static_validation", "All generated files pass static checks", phase=4, depends_on=["code_generation"]),
        Gate("python_syntax", "All .py files have valid Python syntax", phase=5, depends_on=["static_validation"]),
        Gate("json_validation", "All .json files are valid JSON", phase=6, depends_on=["static_validation"]),
        Gate("hooks_validation", "hooks.py is consistent and complete", phase=7, depends_on=["code_generation"]),
        Gate("fixture_validation", "All fixtures are registered and valid", phase=8, depends_on=["json_validation"]),
        Gate("import_validation", "No forbidden imports (erpnext.* in custom app)", phase=9, depends_on=["python_syntax"]),
        Gate("bench_migrate", "bench migrate succeeds", phase=10, depends_on=["code_generation"]),
        Gate("bench_build", "bench build succeeds", phase=11, depends_on=["bench_migrate"]),
        Gate("unit_tests", "All unit tests pass", phase=12, depends_on=["bench_migrate"]),
        Gate("browser_verification", "Browser QA passes (login, CRUD, reports)", phase=13, depends_on=["bench_build"]),
        Gate("analyzer", "Project analyzer reports zero critical issues", phase=14, depends_on=["code_generation"]),
        Gate("zero_critical", "Zero critical issues from all validators", phase=15, depends_on=["analyzer", "static_validation"]),
    ]

    def __init__(self, strict: bool = True):
        self.strict = strict  # If True, stop on first failure
        self.results: dict[str, Gate] = {}
        for g in self.GATES:
            self.results[g.name] = Gate(g.name, g.description, g.phase, g.depends_on[:])

    def get_pending(self) -> list[str]:
        """Get gates that are still pending and have dependencies met."""
        pending = []
        for gate_name, gate in self.results.items():
            if gate.status != GateStatus.PENDING:
                continue
            deps_met = all(
                self.results[d].status == GateStatus.PASSED
                for d in gate.depends_on
            )
            if deps_met:
                pending.append(gate_name)
        return sorted(pending, key=lambda g: self.results[g].phase)

    def pass_gate(self, name: str, detail: str = "", duration_ms: int = 0):
        if name in self.results:
            self.results[name].status = GateStatus.PASSED
            self.results[name].detail = detail
            self.results[name].duration_ms = duration_ms

    def fail_gate(self, name: str, detail: str = ""):
        if name in self.results:
            self.results[name].status = GateStatus.FAILED
            self.results[name].detail = detail

    def skip_gate(self, name: str, reason: str = ""):
        if name in self.results:
            self.results[name].status = GateStatus.SKIPPED
            self.results[name].detail = reason

    def all_passed(self) -> bool:
        return all(
            g.status == GateStatus.PASSED or g.status == GateStatus.SKIPPED
            for g in self.results.values()
        )

    def has_failures(self) -> bool:
        return any(g.status == GateStatus.FAILED for g in self.results.values())

    def failed_gates(self) -> list[str]:
        return [n for n, g in self.results.items() if g.status == GateStatus.FAILED]

    def summary(self) -> dict:
        return {
            "total": len(self.results),
            "passed": sum(1 for g in self.results.values() if g.status == GateStatus.PASSED),
            "failed": sum(1 for g in self.results.values() if g.status == GateStatus.FAILED),
            "skipped": sum(1 for g in self.results.values() if g.status == GateStatus.SKIPPED),
            "pending": sum(1 for g in self.results.values() if g.status == GateStatus.PENDING),
            "gates": {n: {"status": g.status.value, "detail": g.detail} for n, g in self.results.items()},
        }
