"""Phase 3: Artifact Graph Builder

Scans the project filesystem once and builds a complete project model:
  Modules, DocTypes, Child Tables, Reports, Workspaces, Dashboards,
  Fixtures, Hooks, Permissions, Dependency Graph.
"""

import json
import re
from pathlib import Path
from typing import Any

from .hooks_parser import HooksParser  # H7: AST-based parsing replaces regex
from .interfaces import ArtifactGraph, DocTypeDef
from .templates import MODULE_TEMPLATES  # C2: single source of truth


class ArtifactGraphBuilder:
    """Build a complete project model from filesystem scan."""

    def __init__(self):
        self._erpnext_deps: dict[str, list[str]] = {
            "Company": [],
            "Customer": ["Company"],
            "Supplier": ["Company"],
            "Item": ["Company"],
            "Warehouse": ["Company"],
            "Account": ["Company"],
            "Project": ["Company", "Customer"],
            "Employee": ["Company"],
            "Sales Order": ["Customer", "Company", "Item"],
            "Purchase Order": ["Supplier", "Company", "Item"],
            "Quotation": ["Customer", "Company", "Item"],
            "Sales Invoice": ["Customer", "Company", "Sales Order"],
            "Purchase Invoice": ["Supplier", "Company", "Purchase Order"],
            "Delivery Note": ["Customer", "Company", "Sales Order", "Item"],
            "BOM": ["Company", "Item"],
            "Work Order": ["Company", "BOM", "Item"],
            "Job Card": ["Work Order", "Employee"],
            "Timesheet": ["Project", "Employee"],
            "Task": ["Project"],
            "Issue": ["Customer", "Project"],
            "Leave Application": ["Employee"],
            "Expense Claim": ["Employee", "Company"],
            "Quality Inspection": ["Item"],
            "Asset": ["Company", "Item"],
        }

    def build(self, app_path: str) -> ArtifactGraph:
        """Full scan and model construction."""
        root = Path(app_path)
        graph = ArtifactGraph(
            app_name=root.name,
            app_path=str(root),
        )

        graph.modules = self._read_modules(root)
        graph.hooks = self._read_hooks(root)
        graph.patches = self._read_patches(root)
        graph.doctypes = self._scan_doctypes(root, istable=False)
        graph.child_tables = self._scan_doctypes(root, istable=True)
        graph.fixtures = self._scan_fixtures(root)
        graph.workspaces = self._find_by_pattern(root, "**/workspace/*.json")
        graph.reports = self._find_by_pattern(root, "**/report/**/*.json")
        graph.dashboards = self._find_by_pattern(root, "**/dashboard/*.json")
        graph.dependency_order = self._resolve_dependencies(graph)

        return graph

    def _read_modules(self, root: Path) -> list[str]:
        path = root / "modules.txt"
        if not path.exists():
            return []
        return [l.strip() for l in path.read_text().splitlines() if l.strip()]

    def _read_hooks(self, root: Path) -> dict:
        path = root / "hooks.py"
        if not path.exists():
            return {}
        parser = HooksParser.from_file(path)  # H7: AST-based parsing
        return parser.parse_hooks()

    def _read_patches(self, root: Path) -> list[str]:
        path = root / "patches.txt"
        if not path.exists():
            return []
        return [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.startswith("#")]

    def _scan_doctypes(self, root: Path, istable: bool = False) -> dict[str, DocTypeDef]:
        """Scan all DocType JSONs."""
        doctypes: dict[str, DocTypeDef] = {}
        app_module = root / root.name
        if not app_module.exists():
            return doctypes

        for json_file in app_module.rglob("**/doctype/*/*.json"):
            try:
                data = json.loads(json_file.read_text())
                if data.get("doctype") != "DocType":
                    continue
                if data.get("istable", 0) != (1 if istable else 0):
                    continue

                name = data.get("name", "")
                link_fields = [
                    f.get("options", "")
                    for f in data.get("fields", [])
                    if f.get("fieldtype") == "Link" and f.get("options")
                ]

                dt = DocTypeDef(
                    name=name,
                    module=data.get("module", ""),
                    istable=bool(data.get("istable", 0)),
                    is_submittable=bool(data.get("is_submittable", 0)),
                    field_count=len(data.get("fields", [])),
                    fields=data.get("fields", []),
                    link_fields=link_fields,
                    permissions=data.get("permissions", []),
                    file_path=str(json_file.relative_to(root)),
                )

                # Add known ERPNext dependencies
                if name in self._erpnext_deps:
                    for dep in self._erpnext_deps[name]:
                        if dep not in dt.link_fields:
                            dt.link_fields.append(dep)

                doctypes[name] = dt
            except (json.JSONDecodeError, KeyError):
                pass

        return doctypes

    def _scan_fixtures(self, root: Path) -> dict:
        """Scan fixtures directory."""
        fixtures_dir = root / root.name / "fixtures" if (root / root.name).exists() else None
        if not fixtures_dir or not fixtures_dir.exists():
            return {"exists": False, "files": [], "types": []}

        files = list(fixtures_dir.rglob("*.json"))
        types_found: set[str] = set()
        for f in files:
            try:
                data = json.loads(f.read_text())
                if dt := data.get("doctype"):
                    types_found.add(dt)
            except (json.JSONDecodeError, KeyError):
                pass

        return {
            "exists": True,
            "file_count": len(files),
            "files": [str(f.relative_to(root)) for f in files],
            "types": sorted(types_found),
        }

    def _find_by_pattern(self, root: Path, pattern: str) -> list[str]:
        """Find files matching a glob pattern."""
        return [str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file()]

    def _resolve_dependencies(self, graph: ArtifactGraph) -> list[str]:
        """Topological sort of all DocTypes based on Link field dependencies."""
        all_dts = {**graph.doctypes, **graph.child_tables}
        in_degree: dict[str, int] = {}
        adjacency: dict[str, set[str]] = {}

        for name in all_dts:
            in_degree[name] = 0
            adjacency[name] = set()

        for name, dt in all_dts.items():
            for dep in dt.link_fields:
                if dep in all_dts:
                    adjacency[name].add(dep)
                    in_degree[name] = in_degree.get(name, 0) + 1

        # Kahn's algorithm
        queue = [name for name, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for name in all_dts:
                if node in adjacency.get(name, set()):
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        remaining = [n for n in all_dts if n not in result]
        result.extend(remaining)
        return result

    def _find_by_pattern(self, root: Path, pattern: str) -> list[str]:
        """Find files matching a glob pattern."""
        return [str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file()]

    def _resolve_dependencies(self, graph: ArtifactGraph) -> list[str]:
        """Topological sort of all DocTypes based on Link field dependencies."""
        all_dts = {**graph.doctypes, **graph.child_tables}
        in_degree: dict[str, int] = {}
        adjacency: dict[str, set[str]] = {}

        for name in all_dts:
            in_degree[name] = 0
            adjacency[name] = set()

        for name, dt in all_dts.items():
            for dep in dt.link_fields:
                if dep in all_dts:
                    adjacency[name].add(dep)
                    in_degree[name] = in_degree.get(name, 0) + 1

        # Kahn's algorithm
        queue = [name for name, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for name in all_dts:
                if node in adjacency.get(name, set()):
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        remaining = [n for n in all_dts if n not in result]
        result.extend(remaining)
        return result


class TaskPlanner:
    """Phase 3: Generate ordered task list from goal + artifact graph."""

    def plan(self, goal: str, graph: ArtifactGraph) -> list:
        """Generate ordered task list."""
        from .interfaces import Task
        tasks = []
        tid = 0

        # Detect module template
        module_key = None
        goal_lower = goal.lower()
        for key in MODULE_TEMPLATES:
            if key in goal_lower:
                module_key = key
                break

        # Phase 1: Scaffold
        tid += 1
        tasks.append(Task(f"T{tid}", "App scaffold", "Ensure hooks.py, modules.txt, patches.txt exist", "hook"))
        tid += 1
        tasks.append(Task(f"T{tid}", "pyproject.toml", "Ensure pyproject.toml with proper metadata", "hook"))

        # Phase 2: DocTypes (dependency-ordered)
        if module_key:
            tmpl = MODULE_TEMPLATES[module_key]
            all_dts = tmpl["doctypes"] + tmpl["child_tables"]
            builder = ArtifactGraphBuilder()
            # Build a dependency graph from the template
            temp_graph = ArtifactGraph()
            for dt_name in all_dts:
                is_child = dt_name in tmpl["child_tables"]
                target = temp_graph.child_tables if is_child else temp_graph.doctypes
                target[dt_name] = DocTypeDef(name=dt_name, istable=is_child)
            resolved = builder._resolve_dependencies(temp_graph) if len(all_dts) > 1 else all_dts

            for dt_name in resolved:
                is_child = tmpl["child_tables"].__contains__(dt_name)
                tid += 1
                tasks.append(Task(
                    f"T{tid}",
                    f"DocType: {dt_name}",
                    f"Create {'child table ' if is_child else ''}DocType '{dt_name}'",
                    "child_table" if is_child else "doctype",
                    target_name=dt_name,
                ))

        # Phase 3-6: Fixtures, permissions, workspace, reports, dashboards
        dt_ids = [t.id for t in tasks if t.category in ("doctype", "child_table")]
        for cat, name in [("fixture", "Custom Fields"), ("permission", "Role Permissions"),
                           ("workspace", "Workspace"), ("report", "Reports"),
                           ("dashboard", "Dashboard"), ("test", "Unit Tests")]:
            tid += 1
            tasks.append(Task(f"T{tid}", name, f"Create {name.lower()}", cat, depends_on=dt_ids))

        # Phase 7: Docs
        for name in ["README", "CHANGELOG"]:
            tid += 1
            tasks.append(Task(f"T{tid}", name, f"Update {name}", "doc"))

        # Phase 8: Verification
        tid += 1
        tasks.append(Task(f"T{tid}", "Bench migrate", "Run bench migrate", "verify",
                           depends_on=[t.id for t in tasks[:5]]))
        tid += 1
        tasks.append(Task(f"T{tid}", "Analyze", "Run project analyzer", "verify"))
        tid += 1
        tasks.append(Task(f"T{tid}", "Browser QA", "Run browser verification", "verify"))

        return tasks