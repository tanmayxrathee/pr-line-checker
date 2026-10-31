"""Config file extractor for YAML, TOML, JSON, .env.example, INI."""

from __future__ import annotations

from driftcheck.extract.base import FileChange
from driftcheck.models import ChangeFact


class ConfigFilesExtractor:
    """Extract config key changes from config files."""

    name = "config_files"

    def applies_to(self, path: str) -> bool:
        # This is checked via config_globs in the caller
        return True

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        # TODO: Implement in P1.3.1
        return []
