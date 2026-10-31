"""CLI flag extractor for argparse, click, and typer."""

from __future__ import annotations

from driftcheck.extract.base import FileChange
from driftcheck.models import ChangeFact


class CLIExtractor:
    """Extract CLI flags from argparse, click, and typer code."""

    name = "py_cli"

    def applies_to(self, path: str) -> bool:
        return path.endswith(".py")

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        # TODO: Implement in P1.2.1
        return []
