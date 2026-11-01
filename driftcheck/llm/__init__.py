"""LLM package - Tier 2 LLM analysis and verification."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.models import ChangeFact, DocSentence, Finding


def analyze_tier2(
    fact: ChangeFact,
    candidates: list[DocSentence],
    cfg: Config,
) -> list[Finding]:
    """Run Tier 2 LLM analysis for a change fact against candidates.

    Args:
        fact: Code change fact
        candidates: Candidate documentation sentences
        cfg: Configuration

    Returns:
        List of Finding objects
    """
    # TODO: Implement in Phase 2
    return []


def verify_findings(
    findings: list[Finding],
    fact: ChangeFact,
    candidates: list[DocSentence],
    cfg: Config,
) -> list[Finding]:
    """Run LLM verification on findings.

    Args:
        findings: Findings to verify
        fact: Code change fact
        candidates: Candidate documentation sentences
        cfg: Configuration

    Returns:
        List of verified Finding objects
    """
    # TODO: Implement in Phase 2
    return findings
