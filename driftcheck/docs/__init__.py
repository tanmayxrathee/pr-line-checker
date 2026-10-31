"""Docs package - documentation fact extraction."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.gitutil import RepoView
from driftcheck.models import DocSentence


def extract_doc_facts(repo: RepoView, cfg: Config) -> list[DocSentence]:
    """Extract documentation facts from documentation files.

    Args:
        repo: Repository view for reading files at revisions
        cfg: Configuration

    Returns:
        List of DocSentence objects
    """
    # TODO: Implement in Phase 1
    return []
