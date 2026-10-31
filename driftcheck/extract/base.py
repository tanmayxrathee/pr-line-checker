"""Extractor base protocol and shared types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from driftcheck.config import Config
from driftcheck.models import ChangeFact


@dataclass(frozen=True)
class Hunk:
    """A single hunk in a unified diff."""

    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: list[tuple[str, int | None, int | None, str]]  # (tag, old_line_no, new_line_no, text)


@dataclass(frozen=True)
class FileChange:
    """A file change from a unified diff."""

    old_path: str
    new_path: str
    status: str  # added, removed, modified, renamed
    hunks: list[Hunk]

    @property
    def path(self) -> str:
        """Return the primary path (new_path for added/modified, old_path for removed)."""
        return self.new_path if self.status != "removed" else self.old_path


class Extractor(Protocol):
    """Protocol for code change extractors."""

    name: str

    def applies_to(self, path: str) -> bool:
        """Return True if this extractor should run on the given file path."""
        ...

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        """Extract ChangeFacts from a file change.

        Args:
            fc: The FileChange being processed
            old_src: Source code at base revision (None for added files)
            new_src: Source code at head revision (None for removed files)

        Returns:
            List of ChangeFact objects
        """
        ...


def is_doc(path: str, cfg: Config) -> bool:
    """Check if a file is a documentation file per config."""
    from fnmatch import fnmatch

    for pattern in cfg.docs.globs:
        if fnmatch(path, pattern):
            return True
    for pattern in cfg.docs.exclude:
        if fnmatch(path, pattern):
            return False
    return False


def is_test(path: str) -> bool:
    """Check if a file is a test file."""
    from fnmatch import fnmatch

    test_patterns = [
        "tests/**",
        "test_*.py",
        "*_test.py",
        "*_test.go",
        "*.spec.ts",
        "*.spec.js",
        "*.test.ts",
        "*.test.js",
        "**/test/**",
        "**/tests/**",
    ]
    for pattern in test_patterns:
        if fnmatch(path, pattern):
            return True
    return False


def should_extract(path: str, cfg: Config) -> bool:
    """Check if a file should be processed by code extractors."""
    if is_doc(path, cfg):
        return False
    if is_test(path):
        return False
    # Check ignore globs
    from fnmatch import fnmatch

    for pattern in cfg.code.ignore_globs:
        if fnmatch(path, pattern):
            return False
    return True
