"""Search package - BM25 candidate retrieval."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.models import ChangeFact, DocSentence


def retrieve_candidates(
    facts: list[ChangeFact],
    doc_facts: list[DocSentence],
    cfg: Config,
) -> list[tuple[ChangeFact, list[DocSentence]]]:
    """Retrieve candidate documentation facts for each change fact using BM25.

    Args:
        facts: List of code change facts
        doc_facts: List of documentation sentences
        cfg: Configuration

    Returns:
        List of (ChangeFact, [candidate DocSentences]) tuples
    """
    # TODO: Implement in Phase 1
    return []
