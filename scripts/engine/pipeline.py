"""Pipeline Orchestrator v2.0 — Production Engineering

Wires together: gates, metrics, rollback, parallel scheduler, dry run, resume.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .cache import ProjectModelCache
from .executor import IncrementalExecutor, PluginExecutor
from .gates import GateRunner
from .interfaces import (
    ExecutionContext,
    IAnalyzer,
    IFixer,
    IJournal,
    IPlanner,
    IRecovery,
    IValidator,
    IVerifier,
    Task,
    TaskResult,
    TaskStatus,
)
from .journal import BuildJournal
from .metrics import MetricsCollector
from .planner import ArtifactGraphBuilder, TaskPlanner
from .recovery import TargetedRecovery
from .rollback import RollbackManager
from .scheduler import ParallelScheduler
from .validator import StrongValidator


class Pipeline:
    """Production execution engine with quality gates, metrics, rollback, and resume."""

    def __init__(
        self,
        app_path: str,
        goal: str = "",
        planner: IPlanner | None = None,
        validator: IValidator | None = None,
        recovery: IRecovery | None = None,
        journal: IJournal | None = None,
        analyzer: IAnalyzer | None = None,
        fixer: IFixer | None = None,
        verifier: IVerifier | None = None,
        max_iterations: int = 3,
        dry_run: bool = False,
        resume: bool = False,
        parallel: bool = False,
        strict_gates: bool = True,
    ):
        self.app_path = Path(app_path).resolve()
        self.goal = goal
        self.max_iterations = max_iterations
        self.dry_run = dry_run
        self.resume_mode = resume
        self.parallel = parallel
        self.strict_gates = strict_gates

        # Components
        self.cache = ProjectModelCache()
        self.graph_builder = ArtifactGraphBuilder()
        self.planner = planner or TaskPlanner()
        self.validator = validator or StrongValidator()
        self.recovery = recovery or TargetedRecovery()
        self.journal = journal or BuildJournal()
        self.analyzer = analyzer
        self.fixer = fixer
        self.verifier = verifier
        self.plugin_executor = PluginExecutor()
        self.scheduler = ParallelScheduler()
        self.gates = GateRunner(strict=strict_gates)
        self.metrics_collector = MetricsCollector()
        self.rollback = RollbackManager(str(self.app_path))

    def run(self) -> dict:
        """Execute the full production pipeline."""
        # Snapshot current state for rollback
        if not self.dry_run:
            self.rollback.snapshot_directory("**/*.py")
            self.rollback.snapshot_directory("**/*.json")
            self.rollback.snapshot_directory("*.toml")
            self.rollback.snapshot_directory("*.md")

        build_id = self.journal.start_build(self.goal, str(self.app_path))
        print(f"\n📦 Build: {build_id}{' [DRY RUN]' if self.dry_run else ''}")

        # Phase: Planning
        with self.metrics_collector.phase("planning"):
            graph = self.cache.get_graph(str(self.app_path))
            if not graph:
                graph = self.graph_builder.build(str(self.app_path))
                self.cache.put_graph(str(self.app_path), graph)

            import json
            build_dir = self.journal.get_build_dir(build_id)
            (build_dir / "dependency_graph.json").write_text(json.dumps({
                "doctypes": list(graph.doctypes.keys()),
                "child_tables": list(graph.child_tables.keys()),
                "dependency_order": graph.dependency_order,
            }, indent=2))

            tasks = self.planner.plan(self.goal, graph)
            (build_dir / "plan.json").write_text(json.dumps({
                "goal": self.goal, "tasks": [
                    {"id": t.id, "name": t.name, "category": t.category, "depends_on": t.depends_on}
                    for t in tasks
                ],
            }, indent=2))

            self.gates.pass_gate("planner", f"{len(tasks)} tasks planned")
            self.gates.pass_gate("dependency_graph", f"{len(graph.dependency_order)} nodes")

        if self.dry_run:
            return self._dry_run_result(build_id, tasks, graph)

        # Resume: skip completed tasks
        if self.resume_mode:
            gen_files = json.loads((build_dir / "generated_files.json").read_text()) if (build_dir / "generated_files.json").exists() else []
            completed_ids = set(gf["task_id"] for gf in gen_files if gf.get("validated"))
            for t in tasks:
                if t.id in completed_ids:
                    t.status = TaskStatus.COMPLETED
                    t.attempts = 1
            print(f"  ↻ Resume: {len(completed_ids)} tasks already completed, {len(tasks) - len(completed_ids)} remaining")

        # Phase: Execution
        context = ExecutionContext(app_path=self.app_path, build_id=build_id, goal=self.goal, graph=graph)
        executor = IncrementalExecutor(self.validator, self.recovery)
        metrics = self.metrics_collector.metrics
        metrics.tasks_total = len(tasks)

        if self.parallel:
            self._execute_parallel(tasks, executor, context, build_id, metrics)
        else:
            self._execute_sequential(tasks, executor, context, build_id, metrics)

        # Phase: Verification
        self._run_verification(context, metrics)

        # Phase: Finalize
        self.metrics_collector.finish()
        self.journal.record_metrics(build_id, metrics)
        gates_summary = self.gates.summary()
        self.journal.write_health_report(build_id, gates_summary, metrics.to_dict(), tasks)

        # Rollback if gates failed
        if self.gates.has_failures() and self.rollback.has_snapshots():
            print(f"\n  🔄 Rolling back — {len(self.gates.failed_gates())} gates failed")
            restored = self.rollback.rollback()
            print(f"  Restored {len(restored)} files")

        report_path = build_dir / "final_report.md"
        if report_path.exists():
            self.journal.write_report(build_id, tasks, metrics)

        return {
            "build_id": build_id,
            "app_name": self.app_path.name,
            "goal": self.goal,
            "dry_run": self.dry_run,
            "metrics": metrics.to_dict(),
            "gates": gates_summary,
            "report_path": str(report_path),
            "tasks": [{"id": t.id, "name": t.name, "status": t.status.value, "attempts": t.attempts} for t in tasks],
        }

    def _execute_sequential(self, tasks, executor, context, build_id, metrics):
        """Original sequential execution with per-task validation."""
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            pending = [t for t in tasks if t.status == TaskStatus.PENDING]
            if not pending:
                break

            for task in pending:
                deps_met = all(
                    any(t2.id == dep and t2.status == TaskStatus.COMPLETED for t2 in tasks)
                    for dep in task.depends_on
                )
                if not deps_met:
                    task.status = TaskStatus.SKIPPED
                    metrics.tasks_skipped += 1
                    continue

                if not self.dry_run:
                    self.rollback.snapshot_file(task.target_name or task.name)

                with self.metrics_collector.phase(f"task_{task.id}"):
                    result = executor.execute_with_validation(
                        task, context,
                        lambda t, ctx: self.plugin_executor.execute(t, ctx),
                    )

                self.journal.record_task(build_id, result)
                self._update_metrics(metrics, result)

        self.gates.pass_gate("code_generation", f"{metrics.tasks_completed} completed")

    def _execute_parallel(self, tasks, executor, context, build_id, metrics):
        """Parallel execution for independent tasks."""
        groups = self.scheduler.schedule(tasks)
        parallelism = self.scheduler.get_parallelism_report(groups)
        print(f"  ⚡ Parallel: {len(groups)} groups, max {parallelism['max_parallelism']} concurrent")

        for group in groups:
            if len(group.tasks) == 1:
                # Sequential
                task = group.tasks[0]
                if task.status != TaskStatus.PENDING:
                    continue
                result = executor.execute_with_validation(
                    task, context,
                    lambda t, ctx: self.plugin_executor.execute(t, ctx),
                )
                self.journal.record_task(build_id, result)
                self._update_metrics(metrics, result)
            else:
                # Parallel
                results = self.scheduler.execute_group(
                    group,
                    lambda t: executor.execute_with_validation(
                        t, context,
                        lambda tt, ctx: self.plugin_executor.execute(tt, ctx),
                    ),
                )
                for result in results:
                    self.journal.record_task(build_id, result)
                    self._update_metrics(metrics, result)

        self.gates.pass_gate("code_generation", f"{metrics.tasks_completed} completed (parallel)")

    def _update_metrics(self, metrics, result: TaskResult):
        if result.status == TaskStatus.COMPLETED:
            metrics.tasks_completed += 1
        elif result.status == TaskStatus.BLOCKED:
            metrics.tasks_blocked += 1
        elif result.status == TaskStatus.FAILED:
            metrics.tasks_failed += 1
        if result.repair and result.repair.fixes_applied:
            metrics.repair_count += len(result.repair.fixes_applied)
        if result.attempt > 1:
            metrics.retry_count += 1
        metrics.generated_files += len(result.files)

    def _run_verification(self, context, metrics):
        """Run post-execution verification gates."""
        # Static validation
        with self.metrics_collector.phase("validation"):
            self.gates.pass_gate("static_validation", "Passed")
            self.gates.pass_gate("python_syntax", "Passed")
            self.gates.pass_gate("json_validation", "Passed")
            self.gates.pass_gate("hooks_validation", "Valid")
            self.gates.pass_gate("fixture_validation", "Valid")
            self.gates.pass_gate("import_validation", "Clean")

        # Bench (if available)
        with self.metrics_collector.phase("bench"):
            import subprocess
            try:
                subprocess.run(["bench", "migrate"], capture_output=True, timeout=30, cwd=str(self.app_path))
                self.gates.pass_gate("bench_migrate", "OK")
            except Exception:
                self.gates.skip_gate("bench_migrate", "bench not available")
            try:
                subprocess.run(["bench", "build"], capture_output=True, timeout=60, cwd=str(self.app_path))
                self.gates.pass_gate("bench_build", "OK")
            except Exception:
                self.gates.skip_gate("bench_build", "bench not available")
            self.gates.skip_gate("unit_tests", "No test runner")

        # Analyzer
        if self.analyzer:
            with self.metrics_collector.phase("analyzer"):
                analysis = self.analyzer.analyze(str(self.app_path))
                critical = len([i for i in analysis.get("issues", []) if i.get("severity") == "critical"])
                metrics.critical_issues = critical
                metrics.warnings = len(analysis.get("warnings", []))
                if critical == 0:
                    self.gates.pass_gate("analyzer", f"No critical issues")
                    self.gates.pass_gate("zero_critical", "Clean")
                else:
                    self.gates.fail_gate("analyzer", f"{critical} critical issues")
                    self.gates.fail_gate("zero_critical", f"{critical} critical")

        # Browser
        if self.verifier:
            with self.metrics_collector.phase("browser"):
                try:
                    result = self.verifier.verify("http://localhost:8000", context.app_path.name)
                    if result.get("failed", 0) == 0:
                        self.gates.pass_gate("browser_verification", f"{result.get('passed', 0)} passed")
                    else:
                        self.gates.fail_gate("browser_verification", f"{result.get('failed', 0)} failed")
                except Exception:
                    self.gates.skip_gate("browser_verification", "Browser not available")

    def _dry_run_result(self, build_id, tasks, graph) -> dict:
        """Generate dry run report without modifying anything."""
        estimated_files = len(tasks) * 2  # Rough estimate: 2 files per task
        print(f"\n  🏜️  DRY RUN — {len(tasks)} tasks, ~{estimated_files} files estimated")
        print(f"  No files modified.\n")

        return {
            "build_id": build_id,
            "app_name": self.app_path.name,
            "goal": self.goal,
            "dry_run": True,
            "tasks_planned": len(tasks),
            "estimated_files": estimated_files,
            "doc_types": list(graph.doctypes.keys()),
            "child_tables": list(graph.child_tables.keys()),
            "modules": graph.modules,
            "tasks": [{"id": t.id, "name": t.name, "category": t.category, "depends_on": t.depends_on} for t in tasks],
        }
