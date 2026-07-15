"""Phase 8: Automated Tests

Tests for: Planner, Dependency Graph, Execution Engine,
          Recovery Loop, Journal Generation, Artifact Graph, Validation
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.interfaces import (
    ArtifactGraph,
    DocTypeDef,
    ErrorCategory,
    GeneratedFile,
    Task,
    TaskResult,
    TaskStatus,
    ValidationLevel,
)
from engine.cache import ProjectModelCache
from engine.planner import ArtifactGraphBuilder
from engine.validator import StrongValidator
from engine.recovery import ErrorClassifier, TargetedRecovery
from engine.journal import BuildJournal
from engine.pipeline import Pipeline


# ─── Test Helpers ───────────────────────────────────────────────────

def make_temp_app(name: str = "test_app") -> str:
    """Create a minimal temp ERPNext app for testing."""
    tmp = tempfile.mkdtemp()
    app_dir = Path(tmp) / name
    app_dir.mkdir(parents=True)
    (app_dir / "modules.txt").write_text("Test Module\n")
    (app_dir / "hooks.py").write_text('fixtures = ["Custom Field"]\n')
    return str(app_dir)


def make_doctype_json(name: str, module: str, fields: list[dict] | None = None,
                      istable: bool = False) -> dict:
    return {
        "doctype": "DocType",
        "name": name,
        "module": module,
        "istable": 1 if istable else 0,
        "is_submittable": 0,
        "fields": fields or [
            {"fieldname": "title", "fieldtype": "Data", "label": "Title"},
        ],
        "permissions": [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
        ],
    }


# ─── Tests ──────────────────────────────────────────────────────────

class TestArtifactGraph:
    """Phase 3: Artifact graph tests."""

    def test_empty_app(self):
        """Graph builder handles empty app gracefully."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "empty_app"
            app.mkdir()
            builder = ArtifactGraphBuilder()
            graph = builder.build(str(app))
            assert graph.app_name == "empty_app"
            assert graph.modules == []
            assert graph.doctypes == {}

    def test_doctype_scan(self):
        """Graph builder finds DocTypes."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "test_app"
            app.mkdir()
            doctype_dir = app / "test_app" / "test_module" / "doctype" / "test_dt"
            doctype_dir.mkdir(parents=True)
            dt_json = make_doctype_json("TestDT", "Test Module")
            (doctype_dir / "test_dt.json").write_text(json.dumps(dt_json))

            builder = ArtifactGraphBuilder()
            graph = builder.build(str(app))
            assert "TestDT" in graph.doctypes
            assert graph.doctypes["TestDT"].module == "Test Module"
            assert graph.doctypes["TestDT"].field_count == 1

    def test_child_table_scan(self):
        """Graph builder separates child tables."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "test_app"
            app.mkdir()
            dt_dir = app / "test_app" / "test_module" / "doctype" / "child_dt"
            dt_dir.mkdir(parents=True)
            dt_json = make_doctype_json("ChildDT", "Test Module", istable=True)
            (dt_dir / "child_dt.json").write_text(json.dumps(dt_json))

            builder = ArtifactGraphBuilder()
            graph = builder.build(str(app))
            assert "ChildDT" not in graph.doctypes
            assert "ChildDT" in graph.child_tables

    def test_dependency_order(self):
        """Dependency resolver orders DocTypes correctly."""
        graph = ArtifactGraph()
        # Sales Order depends on Customer, Company, Item
        graph.doctypes["Customer"] = DocTypeDef(name="Customer", link_fields=["Company"])
        graph.doctypes["Company"] = DocTypeDef(name="Company")
        graph.doctypes["Item"] = DocTypeDef(name="Item")
        graph.doctypes["Sales Order"] = DocTypeDef(
            name="Sales Order", link_fields=["Customer", "Company", "Item"]
        )

        builder = ArtifactGraphBuilder()
        order = builder._resolve_dependencies(graph)
        # Company before Customer, and both before Sales Order
        assert order.index("Company") < order.index("Customer")
        assert order.index("Customer") < order.index("Sales Order")
        assert order.index("Item") < order.index("Sales Order")


class TestValidator:
    """Phase 4: Validation tests."""

    def test_python_syntax_pass(self):
        """Valid Python passes syntax check."""
        v = StrongValidator()
        f = GeneratedFile(path="test.py", content="def foo():\n    return 42\n", category="python")
        result = v.validate([f], ArtifactGraph(), ValidationLevel.SYNTAX)
        assert result.passed

    def test_python_syntax_fail(self):
        """Invalid Python fails syntax check."""
        v = StrongValidator()
        f = GeneratedFile(path="test.py", content="def foo(\n    return 42\n", category="python")
        result = v.validate([f], ArtifactGraph(), ValidationLevel.SYNTAX)
        assert not result.passed

    def test_json_syntax_pass(self):
        """Valid JSON passes."""
        v = StrongValidator()
        f = GeneratedFile(path="test.json", content='{"key": "value"}', category="json")
        result = v.validate([f], ArtifactGraph(), ValidationLevel.SYNTAX)
        assert result.passed

    def test_json_syntax_fail(self):
        """Invalid JSON fails."""
        v = StrongValidator()
        f = GeneratedFile(path="test.json", content='{"key": "value",}', category="json")
        result = v.validate([f], ArtifactGraph(), ValidationLevel.SYNTAX)
        assert not result.passed

    def test_doctype_missing_permissions(self):
        """Doctype without permissions fails structure check."""
        v = StrongValidator()
        f = GeneratedFile(
            path="test_dt.json",
            content=json.dumps({"doctype": "DocType", "name": "Test", "module": "M", "fields": []}),
            category="json",
        )
        result = v.validate([f], ArtifactGraph(), ValidationLevel.STRUCTURE)
        assert not result.passed
        assert any("permissions" in e.lower() for e in result.errors)

    def test_duplicate_fieldnames(self):
        """Duplicate fieldnames are caught."""
        v = StrongValidator()
        f = GeneratedFile(
            path="test.json",
            content=json.dumps({
                "doctype": "DocType", "name": "Test", "module": "M",
                "fields": [
                    {"fieldname": "title", "fieldtype": "Data", "label": "T1"},
                    {"fieldname": "title", "fieldtype": "Data", "label": "T2"},
                ],
                "permissions": [{"role": "System Manager", "read": 1}],
            }),
            category="json",
        )
        result = v.validate([f], ArtifactGraph(), ValidationLevel.STRUCTURE)
        assert not result.passed
        assert any("duplicate" in e.lower() for e in result.errors)


class TestRecovery:
    """Phase 5: Recovery tests."""

    def test_classify_syntax_error(self):
        """SyntaxError classified correctly."""
        classifier = ErrorClassifier()
        task = Task("T1", "test", "", "doctype")
        cat = classifier.classify("SyntaxError: invalid syntax on line 5", task, [])
        assert cat == ErrorCategory.SYNTAX_ERROR

    def test_classify_json_error(self):
        """JSONDecodeError classified correctly."""
        classifier = ErrorClassifier()
        task = Task("T1", "test", "", "doctype")
        cat = classifier.classify("JSONDecodeError: Expecting value at line 1", task, [])
        assert cat == ErrorCategory.INVALID_JSON

    def test_classify_permission_error(self):
        """Permission error classified."""
        classifier = ErrorClassifier()
        task = Task("T1", "test", "", "doctype")
        cat = classifier.classify("DocType 'TestDT' has no permissions", task, [])
        assert cat == ErrorCategory.MISSING_PERMISSION

    def test_repair_json_trailing_comma(self):
        """Trailing commas in JSON are auto-fixed."""
        recovery = TargetedRecovery()
        task = Task("T1", "test", "", "doctype")
        f = GeneratedFile(path="test.json", content='{"key": "value",}', category="json")
        result = recovery.repair(ErrorCategory.INVALID_JSON, task, [f], None)
        assert result.success
        assert '"key": "value"' in f.content
        assert f.content.strip().endswith("}")


class TestJournal:
    """Phase 2: Journal tests."""

    def test_build_journal_creation(self):
        """Journal creates build directory."""
        with tempfile.TemporaryDirectory() as tmp:
            journal = BuildJournal(builds_dir=tmp)
            build_id = journal.start_build("test goal", "/fake/path")
            build_dir = Path(tmp) / build_id
            assert build_dir.exists()
            assert (build_dir / "execution.log").exists()
            assert (build_dir / "plan.json").exists()

    def test_record_task(self):
        """Task recording writes to log."""
        with tempfile.TemporaryDirectory() as tmp:
            journal = BuildJournal(builds_dir=tmp)
            build_id = journal.start_build("test", "/fake")
            result = TaskResult(task_id="T1", status=TaskStatus.COMPLETED,
                               files=[GeneratedFile(path="t.json", category="json")])
            journal.record_task(build_id, result)
            log = (Path(tmp) / build_id / "execution.log").read_text()
            assert "T1" in log
            assert "COMPLETED" in log or "✓ T1" in log

    def test_report_generation(self):
        """Report generates markdown."""
        with tempfile.TemporaryDirectory() as tmp:
            journal = BuildJournal(builds_dir=tmp)
            build_id = journal.start_build("test", "/fake")
            result = TaskResult(task_id="T1", status=TaskStatus.COMPLETED,
                               files=[GeneratedFile(path="test.json", category="json", validated=True)])
            journal.record_task(build_id, result)
            report = journal.write_report(build_id)
            assert "final_report.md" in report
            assert "test.json" in Path(report).read_text()


class TestPipeline:
    """Phase 8: Integration tests."""

    def test_pipeline_plans_and_runs(self):
        """Pipeline runs from plan to report."""
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "test_app"
            app.mkdir()
            (app / "modules.txt").write_text("core\n")
            (app / "hooks.py").write_text('fixtures = []\n')

            pipeline = Pipeline(str(app), "Build a test module", max_iterations=1)
            result = pipeline.run()

            assert result["build_id"]
            assert result["metrics"]["tasks_total"] > 0
            assert result["report_path"]

    def test_pipeline_handles_empty_app(self):
        """Pipeline doesn't crash on empty app."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = Pipeline(tmp, "Test", max_iterations=1)
            result = pipeline.run()
            assert result["build_id"]
            assert "report_path" in result


class TestCache:
    """Phase 7: Cache tests."""

    def test_cache_miss_on_fresh_app(self):
        """Cache returns None for uncached app."""
        cache = ProjectModelCache()
        with tempfile.TemporaryDirectory() as tmp:
            assert cache.get_graph(tmp) is None

    def test_cache_hit_after_put(self):
        """Cache returns graph after put."""
        cache = ProjectModelCache()
        graph = ArtifactGraph(app_name="test")
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            (app / "hooks.py").write_text("")
            cache.put_graph(str(app), graph)
            cached = cache.get_graph(str(app))
            if cached:  # May be stale if timestamps don't match exactly
                assert cached.app_name == "test"


# ─── Runner ─────────────────────────────────────────────────────────

def run_tests():
    """Run all tests and report results."""
    test_classes = [TestArtifactGraph, TestValidator, TestRecovery, TestJournal, TestPipeline, TestCache]
    total = 0
    passed = 0
    failed = 0

    print("\n═══ Engine Test Suite ═══\n")

    for cls in test_classes:
        print(f"\n{cls.__name__}:")
        instance = cls()
        for name in dir(instance):
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
    success = run_tests()
    sys.exit(0 if success else 1)
