"""Phase 2: Execution Journal

Creates .builds/<timestamp>/ for every build containing:
  plan.json, dependency_graph.json, generated_files.json,
  execution.log, bench.log, browser.log, analyzer.json,
  fixes.json, retries.json, metrics.json, final_report.md
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .interfaces import BuildMetrics, IJournal, Task, TaskResult, TaskStatus
from .metrics import TimingMetrics  # C1: TimingMetrics from metrics module


class BuildJournal(IJournal):
    """Persistent build journal with full audit trail."""

    def __init__(self, builds_dir: str = ".builds"):
        self.builds_dir = Path(builds_dir)
        self.builds_dir.mkdir(parents=True, exist_ok=True)

    def start_build(self, goal: str, app_path: str) -> str:
        """Initialize build directory and return build_id."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        app_name = Path(app_path).resolve().name
        build_id = f"{timestamp}_{app_name}"
        build_dir = self.builds_dir / build_id
        build_dir.mkdir(parents=True, exist_ok=True)

        # Write initial metadata
        meta = {
            "build_id": build_id,
            "goal": goal,
            "app_path": str(Path(app_path).resolve()),
            "started_at": datetime.now().isoformat(),
            "status": "running",
        }
        (build_dir / "plan.json").write_text(json.dumps(meta, indent=2))
        (build_dir / "execution.log").write_text(f"[{datetime.now().isoformat()}] Build started: {goal}\n")
        (build_dir / "dependency_graph.json").write_text("{}")

        return build_id

    def get_build_dir(self, build_id: str) -> Path:
        return self.builds_dir / build_id

    def record_task(self, build_id: str, result: TaskResult):
        """Record a task execution result."""
        build_dir = self.builds_dir / build_id
        if not build_dir.exists():
            return

        # Append to execution log
        status_icon = {"COMPLETED": "✓", "FAILED": "✗", "BLOCKED": "⊘", "SKIPPED": "→"}.get(
            result.status.value.upper(), "?"
        )
        log_line = (
            f"[{datetime.now().isoformat()}] {status_icon} {result.task_id}: {result.status.value}"
            f" (attempt {result.attempt}, {result.duration_ms}ms)"
        )
        if result.error:
            log_line += f" — {result.error[:200]}"
        log_line += "\n"

        with open(build_dir / "execution.log", "a") as f:
            f.write(log_line)

        # Record retries
        if result.attempt > 1:
            retries = self._load_json(build_dir / "retries.json", [])
            retries.append({
                "task_id": result.task_id,
                "attempt": result.attempt,
                "error": result.error,
                "repair": result.repair.fixes_applied if result.repair else [],
            })
            (build_dir / "retries.json").write_text(json.dumps(retries, indent=2))

        # Record generated files
        if result.files:
            gen_files = self._load_json(build_dir / "generated_files.json", [])
            for f in result.files:
                gen_files.append({
                    "task_id": result.task_id,
                    "path": f.path,
                    "category": f.category,
                    "validated": f.validated,
                })
            (build_dir / "generated_files.json").write_text(json.dumps(gen_files, indent=2))

        # Record fixes
        if result.repair and result.repair.fixes_applied:
            fixes = self._load_json(build_dir / "fixes.json", [])
            fixes.append({
                "task_id": result.task_id,
                "fixes": result.repair.fixes_applied,
            })
            (build_dir / "fixes.json").write_text(json.dumps(fixes, indent=2))

    def record_metrics(self, build_id: str, metrics: BuildMetrics | TimingMetrics):  # C1: accept both metrics types
        """Record final build metrics."""
        build_dir = self.builds_dir / build_id
        if not build_dir.exists():
            return
        (build_dir / "metrics.json").write_text(json.dumps(metrics.to_dict(), indent=2, default=str))

    def write_analyzer_result(self, build_id: str, result: dict):
        """Record analyzer output."""
        build_dir = self.builds_dir / build_id
        if build_dir.exists():
            (build_dir / "analyzer.json").write_text(json.dumps(result, indent=2))

    def write_bench_log(self, build_id: str, output: str):
        """Record bench command output."""
        build_dir = self.builds_dir / build_id
        if build_dir.exists():
            (build_dir / "bench.log").write_text(output)

    def write_browser_log(self, build_id: str, output: str):
        """Record browser verification output."""
        build_dir = self.builds_dir / build_id
        if build_dir.exists():
            (build_dir / "browser.log").write_text(output)

    def write_report(self, build_id: str, tasks: list[Task] | None = None,
                     metrics: BuildMetrics | TimingMetrics | None = None,
                     gates_summary: dict | None = None) -> str:
        """Generate unified final_report.md with build summary and health analysis. (H8: consolidated from write_report+write_health_report)"""
        build_dir = self.builds_dir / build_id
        if not build_dir.exists():
            return ""

        # Collect data
        gen_files = self._load_json(build_dir / "generated_files.json", [])
        fixes = self._load_json(build_dir / "fixes.json", [])
        retries = self._load_json(build_dir / "retries.json", [])

        total_files = len(gen_files)
        validated = sum(1 for f in gen_files if f.get("validated"))
        total_fixes = sum(len(f.get("fixes", [])) for f in fixes)
        total_retries = len(retries)

        health = "HEALTHY" if (gates_summary and gates_summary.get("failed", 0) == 0) else "UNHEALTHY"
        if gates_summary and gates_summary.get("failed", 0) > 0 and gates_summary.get("passed", 0) > 0:
            health = "DEGRADED"

        metric_dict = metrics.to_dict() if metrics and hasattr(metrics, 'to_dict') else {}

        report = f"""# Build Report — {build_id}

**Goal:** {self._load_json(build_dir / 'plan.json', {}).get('goal', 'Unknown')}
**Status:** {health}
**Finished:** {datetime.now().isoformat()}

## Summary

- Generated files: {total_files}
- Validated files: {validated} ({int(validated/total_files*100) if total_files else 0}%)
- Fixes applied: {total_fixes}
- Retries: {total_retries}
- Final status: {'✅ Success' if (hasattr(metrics, 'tasks_failed') and metrics.tasks_failed == 0) else '⚠️ Issues found'}

## Quality Gates

"""
        if gates_summary:
            for name, gate in gates_summary.get("gates", {}).items():
                icon = "PASS" if gate["status"] == "passed" else "FAIL" if gate["status"] == "failed" else gate["status"]
                report += f"- {icon}: {name}\n"
            report += f"\n**Result:** {gates_summary['passed']}/{gates_summary['total']} passed, {gates_summary['failed']} failed\n\n"
        else:
            report += "No gate data available.\n\n"

        report += "## Files Generated\n\n"
        for gf in gen_files:
            icon = "✓" if gf.get("validated") else "✗"
            report += f"- {icon} `{gf.get('path', 'unknown')}` ({gf.get('category', '?')}) [T{gf.get('task_id', '?')}]\n"

        if fixes:
            report += "\n## Fixes Applied\n\n"
            for fix in fixes:
                report += f"### T{fix.get('task_id', '?')}\n"
                for f in fix.get("fixes", []):
                    report += f"- {f}\n"
                report += "\n"
        else:
            report += "\n## Fixes Applied\n\nNo fixes were needed.\n"

        if retries:
            report += "\n## Retries\n\n"
            for r in retries:
                report += f"- T{r.get('task_id', '?')}: {r.get('attempt', '?')} attempts — {r.get('error', '')[:100]}\n"
        else:
            report += "\n## Retries\n\nNo retries were needed.\n"

        if metric_dict:
            report += "\n## Performance\n\n"
            for phase in metric_dict.get("phases", []):
                report += f"- {phase['name']}: {phase['duration_ms']}ms\n"
            report += f"\n- Success rate: {metric_dict.get('success_rate', 0)}%\n"
            report += f"- Repairs: {metric_dict.get('repair_count', 0)}\n"
            report += f"- Critical issues: {metric_dict.get('critical_issues', 0)}\n"

        report += "\n## Recommendations\n\n"
        if total_retries > 2:
            report += "- HIGH retries — review error patterns\n"
        if validated < total_files:
            report += f"- {total_files - validated} files failed validation\n"
        if gates_summary and gates_summary.get("failed", 0) > 0:
            report += "- Quality gates failed — fix before proceeding\n"
        if not fixes and not retries:
            report += "- Zero repairs — build clean\n"

        report_path = build_dir / "final_report.md"
        report_path.write_text(report)
        return str(report_path)

    def _load_json(self, path: Path, default: Any) -> Any:
        """Load JSON file or return default."""
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return default
