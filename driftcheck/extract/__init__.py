"""Extract package - code change fact extraction."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.gitutil import RepoView
from driftcheck.models import ChangeFact


def extract_facts(diff_text: str, repo: RepoView, cfg: Config) -> list[ChangeFact]:
    """Extract code change facts from a unified diff.

    Args:
        diff_text: Unified diff text
        repo: Repository view for reading files at revisions
        cfg: Configuration

    Returns:
        List of ChangeFact objects
    """
    # TODO: Implement in Phase 1
    return []
