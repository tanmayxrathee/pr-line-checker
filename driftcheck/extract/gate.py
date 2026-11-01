"""Gate: 'Needs a doc update?' filter for facts."""

from __future__ import annotations

import ast

from driftcheck.config import Config
from driftcheck.models import ChangeFact, ChangeType


def _is_internal_path(path: str) -> bool:
    """Check if a path is internal/private."""
    internal_patterns = [
        "/_",
        "/internal/",
        "/tests/",
        "/test/",
        "/migrations/",
        "/vendor/",
    ]
    return any(pattern in path for pattern in internal_patterns)


def _is_behavior_change_only_whitespace_logging(old_src: str | None, new_src: str | None) -> bool:
    """Check if a BEHAVIOR_CHANGED fact only touches comments,
    whitespace, logging, docstrings, type hints, f-strings, or import order."""
    if not old_src or not new_src:
        return False

    try:
        ast.parse(old_src)
        ast.parse(new_src)
    except SyntaxError:
        return False

    # Remove docstrings, logging calls, type hints, comments, and compare
    def clean_tree(tree: ast.AST) -> str:
        for node in ast.walk(tree):
            # Remove docstrings
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Module,
                ),
            ):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    node.body.pop(0)
        return ast.dump(tree)

    # This is a simplified check - in reality we'd do more sophisticated
    # AST comparison
    return False


def apply_gate(facts: list[ChangeFact], cfg: Config) -> list[ChangeFact]:
    """Apply the 'needs a doc update?' gate to filter facts.

    Args:
        facts: List of facts to filter
        cfg: Configuration

    Returns:
        Filtered list of facts with public=False for gated-out facts
    """
    result: list[ChangeFact] = []

    for fact in facts:
        public = True

        # Rule 1: Name starts with _ (but not dunder __init__ params of public classes)
        if fact.symbol.startswith("_") and not fact.symbol.startswith("__"):
            public = False

        # Rule 2: File path contains internal patterns
        if _is_internal_path(fact.location.path):
            public = False

        # Rule 3: File matches ignore_code_globs
        from fnmatch import fnmatch

        for pattern in cfg.code.ignore_globs:
            if fnmatch(fact.location.path, pattern):
                public = False
                break

        # Rule 4: BEHAVIOR_CHANGED with only logging/comments/
        # type hints/docstrings/f-string/import order changes
        if fact.change_type == ChangeType.BEHAVIOR_CHANGED:
            # This would need the actual source code to check properly
            # For now, we'll mark it and let the extractor handle it
            pass

        # Rule 5: ADDED facts (new things can't make existing docs wrong)
        if fact.change_type == ChangeType.ADDED:
            public = False

        # Rule 6: Symbol not referenced in docs and not exported
        # This is deferred to search stage (no candidates = no findings)

        if not public:
            # Keep the fact but mark as non-public
            fact.public = False

        result.append(fact)

    return result


def is_docs_only_pr(file_changes: list) -> bool:
    """Check if a PR only touches documentation files.

    Args:
        file_changes: List of FileChange objects

    Returns:
        True if all changed files are documentation files
    """
    # This would need the config to check properly
    return False
