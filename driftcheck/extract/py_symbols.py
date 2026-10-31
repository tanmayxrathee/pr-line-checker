"""Python symbols extractor for functions, classes, parameters, constants."""

from __future__ import annotations

from driftcheck.extract.base import FileChange
from driftcheck.models import ChangeFact


class SymbolsExtractor:
    """Extract Python symbols (functions, classes, params, constants)."""

    name = "py_symbols"

    def applies_to(self, path: str) -> bool:
        return path.endswith(".py")

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        # TODO: Implement in P1.2.2
        return []
