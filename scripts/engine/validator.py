"""Phase 4: Strong Validator

Validates generated files at multiple levels:
  SYNTAX: Python/JSON syntax
  STRUCTURE: Required fields present
  REFERENCES: Link fields point to real DocTypes
  PERMISSIONS: Permission arrays valid
  INTEGRATION: hooks.py consistency
"""

import ast
import json
import re
from pathlib import Path

from .interfaces import (
    ArtifactGraph,
    GeneratedFile,
    IValidator,
    ValidationLevel,
    ValidationResult,
)


class StrongValidator(IValidator):
    """Multi-level validator for generated ERPNext files."""

    def validate(
        self,
        files: list[GeneratedFile],
        graph: ArtifactGraph,
        level: ValidationLevel = ValidationLevel.STRUCTURE,
    ) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        checked = 0

        for f in files:
            file_errors, file_warnings = self._validate_file(f, graph, level)
            errors.extend(file_errors)
            warnings.extend(file_warnings)
            checked += 1

        passed = len(errors) == 0
        result = ValidationResult(
            passed=passed,
            level=level,
            errors=errors,
            warnings=warnings,
            files_checked=checked,
        )

        # Update file validation state
        for f in files:
            f.validated = passed
            f.validation_errors = [e for e in errors if f.path in e]

        return result

    def _validate_file(
        self, f: GeneratedFile, graph: ArtifactGraph, level: ValidationLevel
    ) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []

        # Level 1: Syntax
        if level.value >= ValidationLevel.SYNTAX.value:
            if f.category == "python" and f.content:
                if err := self._check_python_syntax(f):
                    errors.append(f"{f.path}: Python syntax error: {err}")
            elif f.category == "json" and f.content:
                if err := self._check_json_syntax(f):
                    errors.append(f"{f.path}: JSON syntax error: {err}")
            elif f.category in ("js", "ts") and f.content:
                if err := self._check_js_syntax(f):
                    warnings.append(f"{f.path}: JS syntax warning: {err}")

        # Level 2: Structure
        if level.value >= ValidationLevel.STRUCTURE.value:
            if f.path.endswith(".json") and f.category == "json" and f.content:
                try:
                    data = json.loads(f.content)
                    struct_errs = self._validate_doctype_structure(f.path, data)
                    errors.extend(struct_errs)
                except json.JSONDecodeError:
                    pass  # Already caught at syntax level

            if f.path == "hooks.py" and f.content:
                hook_errs = self._validate_hooks_content(f.content, graph)
                errors.extend(hook_errs)

        # Level 3: References
        if level.value >= ValidationLevel.REFERENCES.value:
            if f.path.endswith(".json") and f.category == "json" and f.content:
                try:
                    data = json.loads(f.content)
                    ref_errs = self._validate_references(f.path, data, graph)
                    errors.extend(ref_errs)
                except json.JSONDecodeError:
                    pass

        # Level 5: Integration
        if level.value >= ValidationLevel.INTEGRATION.value:
            if f.path == "hooks.py" and f.content:
                int_errs = self._validate_hooks_integration(f.content, graph)
                errors.extend(int_errs)

        return errors, warnings

    # ─── Syntax Checks ──────────────────────────────────────────

    def _check_python_syntax(self, f: GeneratedFile) -> str:
        try:
            ast.parse(f.content)
            return ""
        except SyntaxError as e:
            return f"line {e.lineno}: {e.msg}"

    def _check_json_syntax(self, f: GeneratedFile) -> str:
        try:
            json.loads(f.content)
            return ""
        except json.JSONDecodeError as e:
            return str(e)

    def _check_js_syntax(self, f: GeneratedFile) -> str:
        # Basic checks without a JS parser
        if f.content.count("{") != f.content.count("}"):
            return "unbalanced braces"
        if f.content.count("(") != f.content.count(")"):
            return "unbalanced parentheses"
        return ""

    # ─── Structure Checks ───────────────────────────────────────

    def _validate_doctype_structure(self, path: str, data: dict) -> list[str]:
        errors = []
        name = data.get("name", path)

        # Required top-level fields
        if not data.get("name"):
            errors.append(f"{path}: missing 'name' field")
        if not data.get("module"):
            errors.append(f"{path}: missing 'module' field")
        if "fields" not in data:
            errors.append(f"{path}: missing 'fields' array")
        else:
            fieldnames = set()
            for field in data["fields"]:
                fn = field.get("fieldname", "")
                if not fn:
                    errors.append(f"{path}: field missing 'fieldname'")
                elif fn in fieldnames:
                    errors.append(f"{path}: duplicate fieldname '{fn}'")
                fieldnames.add(fn)
                ft = field.get("fieldtype", "")
                if ft == "Link" and not field.get("options"):
                    errors.append(f"{path}: Link field '{fn}' missing 'options' (target DocType)")
                if ft == "Table" and not field.get("options"):
                    errors.append(f"{path}: Table field '{fn}' missing 'options' (child DocType)")

        # Child tables must have istable
        if not data.get("istable", 0):
            # Main DocType — must have permissions
            perms = data.get("permissions", [])
            if not perms:
                errors.append(f"{path}: DocType '{name}' has no permissions")
            elif not any(p.get("role") == "System Manager" for p in perms):
                errors.append(f"{path}: DocType '{name}' missing System Manager role")

        # Submittable must have amended_from
        if data.get("is_submittable") and not data.get("amended_field"):
            errors.append(f"{path}: submittable DocType '{name}' missing amended_field")

        return errors

    def _validate_hooks_content(self, content: str, graph: ArtifactGraph) -> list[str]:
        errors = []
        # Check for basic structure
        if "fixtures" not in content:
            errors.append("hooks.py: missing 'fixtures' declaration")
        if "doc_events" not in content:
            errors.append("hooks.py: missing 'doc_events' (may be empty)")
        return errors

    # ─── Reference Checks ──────────────────────────────────────

    def _validate_references(self, path: str, data: dict, graph: ArtifactGraph) -> list[str]:
        errors = []
        all_doctypes = set(graph.all_doctypes().keys())

        for field in data.get("fields", []):
            ft = field.get("fieldtype", "")
            target = field.get("options", "")
            if ft == "Link" and target:
                if target not in all_doctypes and target not in self._known_standard_doctypes():
                    errors.append(
                        f"{path}: Link field '{field.get('fieldname')}' → '{target}' — not found in app or ERPNext standard"
                    )
            if ft == "Table" and target:
                if target not in graph.child_tables and target not in graph.doctypes:
                    errors.append(
                        f"{path}: Table field '{field.get('fieldname')}' → '{target}' — child table not found"
                    )

        return errors

    def _validate_hooks_integration(self, content: str, graph: ArtifactGraph) -> list[str]:
        errors = []
        # Check fixture types match actual fixture files
        fixture_match = re.search(r'fixtures\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if fixture_match and graph.fixtures.get("types"):
            registered = set(re.findall(r'"([^"]+)"', fixture_match.group(1)))
            actual = set(graph.fixtures["types"])
            missing = actual - registered
            if missing:
                errors.append(f"hooks.py: fixture types not registered: {', '.join(missing)}")
        return errors

    def _known_standard_doctypes(self) -> set[str]:
        return {
            "DocType", "DocField", "DocPerm", "Role", "User", "Company",
            "Customer", "Supplier", "Item", "Warehouse", "Account",
            "Sales Order", "Purchase Order", "Quotation", "Sales Invoice",
            "Purchase Invoice", "Delivery Note", "Purchase Receipt",
            "Stock Entry", "Journal Entry", "Payment Entry",
            "BOM", "Work Order", "Job Card", "Project", "Task", "Timesheet",
            "Employee", "Leave Application", "Expense Claim",
            "Issue", "Quality Inspection", "Asset", "Asset Movement",
            "Contact", "Address", "Lead", "Opportunity",
            "Custom Field", "Property Setter", "Role Permission",
            "Workspace", "Report", "Dashboard", "Dashboard Chart",
            "Print Format", "Letter Head", "Email Account",
            "Notification", "Scheduled Job", "Error Log",
        }
