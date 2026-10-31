"""Tier 1 package - deterministic drift detection."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.models import ChangeFact, DocSentence, Finding


def detect_tier1(
    fact: ChangeFact,
    candidates: list[DocSentence],
    cfg: Config,
) -> list[Finding]:
    """Run Tier 1 deterministic checks for a change fact against candidates.

    Args:
        fact: Code change fact
        candidates: Candidate documentation sentences
        cfg: Configuration

    Returns:
        List of Finding objects
    """
    # TODO: Implement in Phase 1
    return []
