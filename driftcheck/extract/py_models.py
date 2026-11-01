"""Dataclass/pydantic/attrs field defaults extractor."""

from __future__ import annotations

from driftcheck.extract.base import FileChange
from driftcheck.models import ChangeFact


class ModelsExtractor:
    """Extract field defaults from dataclasses, pydantic models, attrs."""

    name = "py_models"

    def applies_to(self, path: str) -> bool:
        return path.endswith(".py")

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        # TODO: Implement in P1.2.4
        return []
