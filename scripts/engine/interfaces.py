"""ERPNext Execution Engine — Plugin Interfaces (Phase 6)

All components communicate through these abstract interfaces.
The pipeline orchestrates — it does not implement ERPNext logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ─── Data Structures ────────────────────────────────────────────────

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"

class ErrorCategory(Enum):
    SYNTAX_ERROR = "syntax_error"
    MISSING_FILE = "missing_file"
    MISSING_PERMISSION = "missing_permission"
    BROKEN_REFERENCE = "broken_reference"
    DUPLICATE_NAME = "duplicate_name"
    INVALID_JSON = "invalid_json"
    INVALID_HOOK = "invalid_hook"
    IMPORT_ERROR = "import_error"
    DEPENDENCY_FAILURE = "dependency_failure"
    BENCH_ERROR = "bench_error"
    BROWSER_ERROR = "browser_error"
    UNKNOWN = "unknown"

class ValidationLevel(Enum):
    SYNTAX = 1       # Python/JSON/TS syntax check
    STRUCTURE = 2    # Required fields present
    REFERENCES = 3   # Link fields point to real DocTypes
    PERMISSIONS = 4  # Permission arrays valid
    INTEGRATION = 5  # hooks.py consistency, fixture registration


@dataclass
class DocTypeDef:
    """Structured representation of a DocType."""
    name: str
    module: str = ""
    istable: bool = False
    is_submittable: bool = False
    field_count: int = 0
    fields: list[dict] = field(default_factory=list)
    link_fields: list[str] = field(default_factory=list)
    permissions: list[dict] = field(default_factory=list)
    file_path: str = ""

    def depends_on(self) -> list[str]:
        """Return DocType names this DocType links to."""
        return self.link_fields


@dataclass
class ArtifactGraph:
    """Complete project model (Phase 3)."""
    app_name: str = ""
    app_path: str = ""
    modules: list[str] = field(default_factory=list)
    doctypes: dict[str, DocTypeDef] = field(default_factory=dict)
    child_tables: dict[str, DocTypeDef] = field(default_factory=dict)
    hooks: dict = field(default_factory=dict)
    patches: list[str] = field(default_factory=list)
    fixtures: dict = field(default_factory=dict)
    workspaces: list[str] = field(default_factory=list)
    reports: list[str] = field(default_factory=list)
    dashboards: list[str] = field(default_factory=list)
    dependency_order: list[str] = field(default_factory=list)

    def all_doctypes(self) -> dict[str, DocTypeDef]:
        return {**self.doctypes, **self.child_tables}

    def get_dependencies(self, name: str) -> list[str]:
        """Get all transitive dependencies of a DocType."""
        seen: set[str] = set()
        result: list[str] = []

        def walk(n: str):
            if n in seen:
                return
            seen.add(n)
            dt = self.all_doctypes().get(n)
            if dt:
                for dep in dt.depends_on():
                    walk(dep)
                    if dep not in result:
                        result.append(dep)

        walk(name)
        return result


@dataclass
class Task:
    """A single unit of work in the execution pipeline."""
    id: str
    name: str
    description: str
    category: str  # doctype, child_table, fixture, hook, permission, workspace, report, dashboard, test, doc, verify
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    errors: list[str] = field(default_factory=list)
    max_attempts: int = 3
    target_name: str = ""  # DocType name, module name, etc.


@dataclass
class GeneratedFile:
    """A file produced by task execution."""
    path: str          # relative to app root
    content: str = ""
    category: str = ""  # json, python, js, css, md, toml, txt
    validated: bool = False
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of validating generated files."""
    passed: bool
    level: ValidationLevel = ValidationLevel.SYNTAX
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files_checked: int = 0


@dataclass
class RepairResult:
    """Result of a repair attempt."""
    success: bool
    fixes_applied: list[str] = field(default_factory=list)
    error_detail: str = ""


@dataclass
class TaskResult:
    """Complete result of executing a single task."""
    task_id: str
    status: TaskStatus
    files: list[GeneratedFile] = field(default_factory=list)
    validation: ValidationResult | None = None
    repair: RepairResult | None = None
    error: str = ""
    duration_ms: int = 0
    attempt: int = 1


@dataclass
class BuildMetrics:
    """Build performance metrics."""
    total_duration_ms: int = 0
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_blocked: int = 0
    tasks_skipped: int = 0
    repairs_attempted: int = 0
    repairs_succeeded: int = 0
    validations_run: int = 0
    validations_passed: int = 0
    files_generated: int = 0
    files_validated: int = 0
    iterations: int = 0


@dataclass
class ExecutionContext:
    """Context passed through the execution pipeline."""
    app_path: Path
    build_id: str
    goal: str
    graph: ArtifactGraph
    site_url: str = "http://localhost:8000"
    headless: bool = False


# ─── Interfaces ─────────────────────────────────────────────────────

class IPlanner(ABC):
    """Phase 3: Plan tasks from goal + artifact graph."""

    @abstractmethod
    def plan(self, goal: str, graph: ArtifactGraph) -> list[Task]:
        """Generate ordered task list with dependencies."""
        ...


class IExecutor(ABC):
    """Phase 1: Execute a single task, producing validated files."""

    @abstractmethod
    def execute(self, task: Task, context: ExecutionContext) -> list[GeneratedFile]:
        """Execute one task. Returns generated files (not yet validated)."""
        ...


class IValidator(ABC):
    """Phase 4: Validate generated files at multiple levels."""

    @abstractmethod
    def validate(
        self,
        files: list[GeneratedFile],
        graph: ArtifactGraph,
        level: ValidationLevel = ValidationLevel.STRUCTURE,
    ) -> ValidationResult:
        """Validate files. Returns result with errors/warnings."""
        ...


class IRecovery(ABC):
    """Phase 5: Classify errors and attempt targeted repairs."""

    @abstractmethod
    def classify(self, error: str, task: Task, files: list[GeneratedFile]) -> ErrorCategory:
        """Classify the error into a known category."""
        ...

    @abstractmethod
    def repair(
        self,
        category: ErrorCategory,
        task: Task,
        files: list[GeneratedFile],
        context: ExecutionContext,
    ) -> RepairResult:
        """Attempt a targeted repair based on error category."""
        ...


class IJournal(ABC):
    """Phase 2: Persistent build journal."""

    @abstractmethod
    def start_build(self, goal: str, app_path: str) -> str:
        """Initialize build journal. Returns build_id."""
        ...

    @abstractmethod
    def record_task(self, build_id: str, result: TaskResult):
        """Record a task execution result."""
        ...

    @abstractmethod
    def record_metrics(self, build_id: str, metrics: BuildMetrics):
        """Record final build metrics."""
        ...

    @abstractmethod
    def write_report(self, build_id: str) -> str:
        """Generate final_report.md. Returns path."""
        ...

    @abstractmethod
    def get_build_dir(self, build_id: str) -> Path:
        """Get the build directory path."""
        ...


class ICache(ABC):
    """Phase 7: Filesystem cache to avoid repeated scans."""

    @abstractmethod
    def get_graph(self, app_path: str) -> ArtifactGraph | None:
        """Get cached artifact graph if fresh."""
        ...

    @abstractmethod
    def put_graph(self, app_path: str, graph: ArtifactGraph):
        """Cache the artifact graph."""
        ...

    @abstractmethod
    def invalidate(self, app_path: str, file_path: str):
        """Invalidate cache entries affected by file change."""
        ...

    @abstractmethod
    def is_fresh(self, app_path: str) -> bool:
        """Check if cache is still valid."""
        ...


class IAnalyzer(ABC):
    """Project analyzer — detects issues in existing app."""

    @abstractmethod
    def analyze(self, app_path: str) -> dict:
        """Run analysis. Returns dict with 'issues', 'warnings', 'stats'."""
        ...


class IFixer(ABC):
    """Auto-fixer — repairs common issues."""

    @abstractmethod
    def fix(self, app_path: str) -> dict:
        """Run auto-fix. Returns dict with 'fixes_applied', 'fixes_skipped'."""
        ...


class IVerifier(ABC):
    """Browser verification — tests app through the browser."""

    @abstractmethod
    def verify(self, site_url: str, app_name: str, headless: bool = False) -> dict:
        """Run browser verification. Returns dict with 'results', 'passed', 'failed'."""
        ...
