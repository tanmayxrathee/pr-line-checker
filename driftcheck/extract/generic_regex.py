"""Generic regex fallback extractor for JS/TS/Go/Rust/shell."""

from __future__ import annotations

from driftcheck.extract.base import FileChange
from driftcheck.models import ChangeFact


class GenericRegexExtractor:
    """Generic regex-based extraction for non-Python languages."""

    name = "generic_regex"

    def applies_to(self, path: str) -> bool:
        # Applies to non-Python files
        return not path.endswith(".py")

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        # TODO: Implement in P1.3.2
        return []
