"""Environment variable extractor for os.getenv, os.environ, pydantic-settings."""

from __future__ import annotations

from driftcheck.extract.base import FileChange
from driftcheck.models import ChangeFact


class EnvExtractor:
    """Extract environment variable accesses."""

    name = "py_env"

    def applies_to(self, path: str) -> bool:
        return path.endswith(".py")

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        # TODO: Implement in P1.2.3
        return []
