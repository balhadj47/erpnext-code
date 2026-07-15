"""HooksParser — Robust Python hooks.py parsing using ast (H7).

Replaces regex-based parsing (planner.py, erpnext_analyzer.py) with
AST parsing for correct handling of nested brackets, multi-line dicts,
and comments inside lists.
"""

import ast
from pathlib import Path


class HooksParser:
    """Parse ERPNext hooks.py files using Python's AST module.

    Handles fixtures, doc_events, scheduler_events, website_context,
    jenv, app_include_js, app_include_css, override_doctype_class.
    """

    def __init__(self, content: str):
        self._content = content
        try:
            self._tree = ast.parse(content)
        except SyntaxError:
            self._tree = None

    @classmethod
    def from_file(cls, path: str | Path) -> "HooksParser":
        path = Path(path)
        return cls(path.read_text())

    def extract_list(self, key: str) -> list:
        """Extract a Python list assigned to a variable name.

        Returns a list of string values (strip quotes).
        """
        if self._tree is None:
            return []
        for node in ast.walk(self._tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == key:
                        if isinstance(node.value, ast.List):
                            return self._eval_constant(node.value)
        return []

    def extract_dict_keys(self, key: str) -> list:
        """Extract top-level string keys from a dict assigned to a variable.

        Returns a list of key strings.
        """
        if self._tree is None:
            return []
        for node in ast.walk(self._tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == key:
                        if isinstance(node.value, ast.Dict):
                            return [
                                k.value
                                for k in node.value.keys
                                if isinstance(k, ast.Constant) and isinstance(k.value, str)
                            ]
        return []

    def parse_hooks(self) -> dict:
        """Parse all standard hooks from hooks.py content.

        Returns a dict with: fixtures, doc_events, scheduler_events,
        website_context, jenv, app_include_js, app_include_css,
        override_doctype_class.
        """
        return {
            "fixtures": self.extract_list("fixtures"),
            "doc_events": self.extract_dict_keys("doc_events"),
            "scheduler_events": self.extract_dict_keys("scheduler_events"),
            "website_context": self.extract_dict_keys("website_context"),
            "jenv": self.extract_dict_keys("jenv"),
            "app_include_js": self.extract_list("app_include_js"),
            "app_include_css": self.extract_list("app_include_css"),
            "override_doctype_class": self.extract_dict_keys("override_doctype_class"),
        }

    @staticmethod
    def _eval_constant(node: ast.List) -> list:
        """Evaluate a list of string constants from AST nodes.

        Handles str, int, float, and simple concatenation.
        """
        result = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant):
                if isinstance(elt.value, str):
                    result.append(elt.value)
                else:
                    result.append(elt.value)
            elif isinstance(elt, ast.JoinedStr):
                # f-strings: extract literal parts only
                parts = []
                for val in elt.values:
                    if isinstance(val, ast.Constant):
                        parts.append(str(val.value))
                result.append("".join(parts))
        return result
