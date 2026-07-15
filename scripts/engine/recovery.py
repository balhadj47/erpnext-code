"""Phase 5: Error Classification & Targeted Recovery

Classifies errors into known categories and applies targeted repairs.
If repeated failure (3+ attempts on same task), marks BLOCKED and continues.
"""

from .interfaces import (
    ErrorCategory,
    ExecutionContext,
    GeneratedFile,
    IRecovery,
    RepairResult,
    Task,
)


class ErrorClassifier:
    """Classify error strings into categories."""

    _PATTERNS: dict[str, ErrorCategory] = {
        "SyntaxError": ErrorCategory.SYNTAX_ERROR,
        "invalid syntax": ErrorCategory.SYNTAX_ERROR,
        "JSONDecodeError": ErrorCategory.INVALID_JSON,
        "Expecting value": ErrorCategory.INVALID_JSON,
        "missing.*__init__": ErrorCategory.MISSING_FILE,
        "not found": ErrorCategory.MISSING_FILE,
        "No such file": ErrorCategory.MISSING_FILE,
        "missing permissions": ErrorCategory.MISSING_PERMISSION,
        "no permissions": ErrorCategory.MISSING_PERMISSION,
        "does not point to": ErrorCategory.BROKEN_REFERENCE,
        "not found in app": ErrorCategory.BROKEN_REFERENCE,
        "duplicate": ErrorCategory.DUPLICATE_NAME,
        "already exists": ErrorCategory.DUPLICATE_NAME,
        "fixtures.*not registered": ErrorCategory.INVALID_HOOK,
        "hooks.py": ErrorCategory.INVALID_HOOK,
        "ImportError": ErrorCategory.IMPORT_ERROR,
        "ModuleNotFoundError": ErrorCategory.IMPORT_ERROR,
        "bench.*error": ErrorCategory.BENCH_ERROR,
        "migration.*fail": ErrorCategory.BENCH_ERROR,
        "browser.*error": ErrorCategory.BROWSER_ERROR,
        "login.*fail": ErrorCategory.BROWSER_ERROR,
        "dependency.*fail": ErrorCategory.DEPENDENCY_FAILURE,
    }

    @classmethod
    def classify(cls, error: str, task: Task, files: list[GeneratedFile]) -> ErrorCategory:
        """Classify error string into a category."""
        import re
        error_lower = error.lower()

        for pattern, category in cls._PATTERNS.items():
            if re.search(pattern.lower(), error_lower):
                return category

        # Heuristic: check files
        json_files = [f for f in files if f.category == "json"]
        if json_files and any("json" in e.lower() for e in task.errors):
            return ErrorCategory.INVALID_JSON

        python_files = [f for f in files if f.category == "python"]
        if python_files and any("syntax" in e.lower() for e in task.errors):
            return ErrorCategory.SYNTAX_ERROR

        return ErrorCategory.UNKNOWN


class TargetedRecovery(IRecovery):
    """Apply targeted repairs based on error category."""

    def __init__(self):
        self.classifier = ErrorClassifier()

    def classify(self, error: str, task: Task, files: list[GeneratedFile]) -> ErrorCategory:
        return self.classifier.classify(error, task, files)

    def repair(
        self,
        category: ErrorCategory,
        task: Task,
        files: list[GeneratedFile],
        context: ExecutionContext,
    ) -> RepairResult:
        """Apply targeted repair based on error category."""

        handlers = {
            ErrorCategory.SYNTAX_ERROR: self._repair_syntax,
            ErrorCategory.INVALID_JSON: self._repair_json,
            ErrorCategory.MISSING_PERMISSION: self._repair_permissions,
            ErrorCategory.BROKEN_REFERENCE: self._repair_reference,
            ErrorCategory.INVALID_HOOK: self._repair_hooks,
            ErrorCategory.IMPORT_ERROR: self._repair_imports,
            ErrorCategory.MISSING_FILE: self._repair_missing_file,
        }

        handler = handlers.get(category, self._repair_generic)
        return handler(task, files, context)

    def _repair_syntax(self, task: Task, files: list[GeneratedFile], ctx: ExecutionContext) -> RepairResult:
        fixes = []
        for f in files:
            if f.category == "python":
                # Attempt auto-indent fix
                lines = f.content.split("\n")
                fixed_lines = []
                for line in lines:
                    if line.strip() and not line.startswith((" ", "\t", "def ", "class ", "import ", "from ", "@", "#")):
                        line = "    " + line
                    fixed_lines.append(line)
                new_content = "\n".join(fixed_lines)
                if new_content != f.content:
                    f.content = new_content
                    fixes.append(f"Fixed indentation in {f.path}")
            elif f.category == "json":
                # Try to strip trailing commas
                import re
                new_content = re.sub(r",(\s*[}\]])", r"\1", f.content)
                if new_content != f.content:
                    f.content = new_content
                    fixes.append(f"Removed trailing commas in {f.path}")
        return RepairResult(success=len(fixes) > 0, fixes_applied=fixes)

    def _repair_json(self, task: Task, files: list[GeneratedFile], ctx: ExecutionContext) -> RepairResult:
        fixes = []
        for f in files:
            if f.category == "json":
                import json, re
                try:
                    json.loads(f.content)
                except json.JSONDecodeError:
                    # Try common fixes
                    content = f.content.strip()
                    # Strip markdown fences
                    content = re.sub(r'^```(?:json)?\s*\n?', '', content)
                    content = re.sub(r'\n?```\s*$', '', content)
                    # Strip trailing commas
                    content = re.sub(r",(\s*[}\]])", r"\1", content)
                    try:
                        json.loads(content)
                        f.content = json.dumps(json.loads(content), indent=2)
                        fixes.append(f"Reformatted JSON in {f.path}")
                    except json.JSONDecodeError:
                        pass
        return RepairResult(success=len(fixes) > 0, fixes_applied=fixes)

    def _repair_permissions(self, task: Task, files: list[GeneratedFile], ctx: ExecutionContext) -> RepairResult:
        fixes = []
        import json
        for f in files:
            if f.category == "json" and "doctype" in f.path:
                try:
                    data = json.loads(f.content)
                    if data.get("doctype") == "DocType" and not data.get("istable"):
                        if not data.get("permissions"):
                            data["permissions"] = [
                                {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
                            ]
                            f.content = json.dumps(data, indent=2)
                            fixes.append(f"Added System Manager permissions to {f.path}")
                except json.JSONDecodeError:
                    pass
        return RepairResult(success=len(fixes) > 0, fixes_applied=fixes)

    def _repair_reference(self, task: Task, files: list[GeneratedFile], ctx: ExecutionContext) -> RepairResult:
        # References can't be auto-fixed without knowing the correct target
        return RepairResult(success=False, error_detail="Broken references require manual correction")

    def _repair_hooks(self, task: Task, files: list[GeneratedFile], ctx: ExecutionContext) -> RepairResult:
        fixes = []
        import re
        for f in files:
            if f.path == "hooks.py":
                # Add missing fixture types
                actual_types = ctx.graph.fixtures.get("types", [])
                match = re.search(r'(fixtures\s*=\s*\[)(.*?)(\])', f.content, re.DOTALL)
                if match:
                    existing = set(re.findall(r'"([^"]+)"', match.group(2)))
                    missing = set(actual_types) - existing
                    if missing:
                        all_types = sorted(existing | missing)
                        new_list = "fixtures = [\n    " + ",\n    ".join(f'"{t}"' for t in all_types) + ",\n]"
                        f.content = re.sub(r'fixtures\s*=\s*\[.*?\]', new_list, f.content, flags=re.DOTALL)
                        fixes.append(f"Added missing fixture types: {', '.join(missing)}")
                else:
                    # No fixtures array at all — add one
                    if actual_types:
                        new_fixtures = "fixtures = [\n    " + ",\n    ".join(f'"{t}"' for t in sorted(actual_types)) + ",\n]\n"
                        f.content = new_fixtures + "\n" + f.content
                        fixes.append(f"Added fixtures declaration with {len(actual_types)} types")
        return RepairResult(success=len(fixes) > 0, fixes_applied=fixes)

    def _repair_imports(self, task: Task, files: list[GeneratedFile], ctx: ExecutionContext) -> RepairResult:
        fixes = []
        import re
        for f in files:
            if f.category == "python":
                # Remove erpnext imports
                new_content = re.sub(r'^from erpnext\..*$', '# REMOVED: from erpnext import', f.content, flags=re.MULTILINE)
                if new_content != f.content:
                    f.content = new_content
                    fixes.append(f"Removed erpnext.* imports from {f.path}")
        return RepairResult(success=len(fixes) > 0, fixes_applied=fixes)

    def _repair_missing_file(self, task: Task, files: list[GeneratedFile], ctx: ExecutionContext) -> RepairResult:
        fixes = []
        for f in files:
            if "__init__.py" in f.path and not f.content:
                f.content = "# Auto-generated\n"
                fixes.append(f"Created {f.path}")
        return RepairResult(success=len(fixes) > 0, fixes_applied=fixes)

    def _repair_generic(self, task: Task, files: list[GeneratedFile], ctx: ExecutionContext) -> RepairResult:
        # Fallback: validate JSON files
        return self._repair_json(task, files, ctx)
