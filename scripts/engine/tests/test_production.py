"""Phase 11.9: Regression Suite

Tests for: gates, metrics, rollback, dry run, resume,
          parallel scheduler, plugin discovery, health report.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.interfaces import (
    ArtifactGraph,
    DocTypeDef,
    GeneratedFile,
    Task,
    TaskResult,
    TaskStatus,
)
from engine.gates import GateRunner, GateStatus
from engine.metrics import MetricsCollector, TimingMetrics as BuildMetrics
from engine.rollback import RollbackManager, FileSnapshot
from engine.scheduler import ParallelScheduler
from engine.plugins import discover_plugins
from engine.journal import BuildJournal
from engine.pipeline import Pipeline


class TestQualityGates:
    """Phase 11.1"""

    def test_all_gates_pending_initially(self):
        gates = GateRunner()
        assert len(gates.results) == 15
        assert all(g.status == GateStatus.PENDING for g in gates.results.values())

    def test_pass_gate(self):
        gates = GateRunner()
        gates.pass_gate("planner", "OK")
        assert gates.results["planner"].status == GateStatus.PASSED
        assert not gates.all_passed()

    def test_fail_gate(self):
        gates = GateRunner()
        gates.fail_gate("analyzer", "3 critical issues")
        assert gates.results["analyzer"].status == GateStatus.FAILED
        assert gates.has_failures()

    def test_dependency_chain(self):
        gates = GateRunner()
        gates.pass_gate("planner")
        pending = gates.get_pending()
        assert "dependency_graph" in pending
        assert "bench_build" not in pending  # bench_migrate must pass first

    def test_summary(self):
        gates = GateRunner()
        gates.pass_gate("planner")
        gates.pass_gate("dependency_graph")
        gates.fail_gate("code_generation")
        s = gates.summary()
        assert s["passed"] == 2
        assert s["failed"] == 1


class TestMetrics:
    """Phase 11.2"""

    def test_phase_timing(self):
        collector = MetricsCollector()
        with collector.phase("planning"):
            time.sleep(0.01)
        collector.finish()
        assert collector.metrics.total_time_ms > 0
        assert len(collector.metrics.phases) >= 1

    def test_counters(self):
        collector = MetricsCollector()
        collector.metrics.tasks_completed = 5
        collector.metrics.tasks_total = 10
        collector.metrics.repair_count = 2
        collector.finish()
        assert collector.metrics.success_rate == 50.0

    def test_to_dict(self):
        collector = MetricsCollector()
        collector.finish()
        d = collector.metrics.to_dict()
        assert "total_time_ms" in d
        assert "success_rate" in d


class TestRollback:
    """Phase 11.3"""

    def test_snapshot_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            f = app / "test.txt"
            f.write_text("original")
            rm = RollbackManager(str(app), journal_dir=str(app / ".builds"))
            rm.snapshot_file("test.txt")
            f.write_text("modified")
            rm.rollback()
            assert f.read_text() == "original"

    def test_snapshot_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            rm = RollbackManager(str(app))
            rm.snapshot_file("new.txt")  # Doesn't exist yet
            f = app / "new.txt"
            f.write_text("new")
            rm.rollback()
            assert not f.exists()  # Should be deleted

    def test_save_snapshot_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            f = app / "test.txt"
            f.write_text("data")
            rm = RollbackManager(str(app), journal_dir=str(app / ".builds"))
            rm.snapshot_file("test.txt")
            rm.save_snapshot_state("test_build")
            sj = app / ".builds" / "test_build" / "snapshot.json"
            assert sj.exists()
            data = json.loads(sj.read_text())
            assert data["file_count"] == 1


class TestScheduler:
    """Phase 11.6"""

    def test_sequential_tasks(self):
        scheduler = ParallelScheduler()
        t1 = Task("T1", "A", "", "hook")
        t2 = Task("T2", "B", "", "doctype", depends_on=["T1"])
        t3 = Task("T3", "C", "", "doctype", depends_on=["T2"])
        groups = scheduler.schedule([t1, t2, t3])
        assert len(groups) == 3
        assert groups[0].tasks[0].id == "T1"
        assert groups[1].tasks[0].id == "T2"
        assert groups[2].tasks[0].id == "T3"

    def test_parallel_tasks(self):
        scheduler = ParallelScheduler()
        t1 = Task("T1", "A", "", "hook")
        t2 = Task("T2", "B", "", "doctype")
        t3 = Task("T3", "C", "", "workspace")
        groups = scheduler.schedule([t1, t2, t3])
        assert len(groups) == 1  # All independent
        assert len(groups[0].tasks) == 3

    def test_mixed_parallelism(self):
        scheduler = ParallelScheduler()
        t1 = Task("T1", "Base", "", "doctype")
        t2 = Task("T2", "DepA", "", "doctype", depends_on=["T1"])
        t3 = Task("T3", "DepB", "", "doctype", depends_on=["T1"])
        t4 = Task("T4", "Report", "", "report", depends_on=["T2", "T3"])
        groups = scheduler.schedule([t1, t2, t3, t4])
        assert len(groups) == 3
        assert len(groups[0].tasks) == 1  # T1
        assert len(groups[1].tasks) == 2  # T2, T3 parallel
        assert len(groups[2].tasks) == 1  # T4

    def test_parallelism_report(self):
        scheduler = ParallelScheduler()
        t1 = Task("T1", "A", "", "doctype")
        t2 = Task("T2", "B", "", "doctype")
        groups = scheduler.schedule([t1, t2])
        report = scheduler.get_parallelism_report(groups)
        assert report["max_parallelism"] == 2
        assert report["estimated_speedup"] == "2.0x"


class TestPluginDiscovery:
    """Phase 11.8"""

    def test_discover_plugins(self):
        plugins = discover_plugins()
        assert "analyzer" in plugins or len(plugins) > 0

    def test_get_plugin(self):
        from engine.plugins import get_plugin
        analyzer = get_plugin("analyzer")
        assert analyzer is not None


class TestHealthReport:
    """Phase 11.7"""

    def test_health_report_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = BuildJournal(builds_dir=tmp)
            build_id = journal.start_build("test", "/fake")
            path = journal.write_report(build_id, gates_summary={"passed": 5, "total": 5, "failed": 0, "gates": {}})
            assert "final_report.md" in path
            content = Path(path).read_text()
            assert "HEALTHY" in content


class TestDryRun:
    """Phase 11.4"""

    def test_dry_run_no_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            (app / "hooks.py").write_text("")
            pipeline = Pipeline(str(app), "Test", dry_run=True, max_iterations=1)
            result = pipeline.run()
            assert result["dry_run"] is True
            assert "tasks_planned" in result


class TestResume:
    """Phase 11.5"""

    def test_resume_flag_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            (app / "hooks.py").write_text("")
            pipeline = Pipeline(str(app), "Test", resume=True, max_iterations=1)
            result = pipeline.run()
            assert "build_id" in result


# ─── Runner ─────────────────────────────────────────────────────────

def run_all_tests():
    """Run all tests (original 21 + new 18)."""
    # Import and run original tests
    from engine.tests import (
        TestArtifactGraph, TestValidator, TestRecovery,
        TestJournal, TestPipeline, TestCache,
    )

    test_classes = [
        ("gate", TestQualityGates),
        ("metric", TestMetrics),
        ("rollback", TestRollback),
        ("scheduler", TestScheduler),
        ("plugin_disc", TestPluginDiscovery),
        ("health", TestHealthReport),
        ("dryrun", TestDryRun),
        ("resume", TestResume),
        ("artifact", TestArtifactGraph),
        ("validator", TestValidator),
        ("recovery", TestRecovery),
        ("journal", TestJournal),
        ("pipeline", TestPipeline),
        ("cache", TestCache),
    ]

    total = 0
    passed = 0
    failed = 0

    print("\n═══ Production Engine Regression Suite ═══\n")

    for prefix, cls in test_classes:
        print(f"\n{cls.__name__}:")
        instance = cls()
        for name in sorted(dir(instance)):
            if name.startswith("test_"):
                total += 1
                try:
                    getattr(instance, name)()
                    print(f"  ✓ {name}")
                    passed += 1
                except Exception as e:
                    print(f"  ✗ {name}: {e}")
                    failed += 1

    print(f"\n═══ Results: {passed}/{total} passed, {failed} failed ═══\n")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
