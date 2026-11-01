"""Filters package - finding deduplication and suppression."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.models import Finding


def deduplicate_findings(findings: list[Finding], cfg: Config) -> list[Finding]:
    """Deduplicate findings.

    Args:
        findings: List of findings
        cfg: Configuration

    Returns:
        Deduplicated list of findings
    """
    # TODO: Implement in Phase 1
    return findings


def suppress_known_issues(findings: list[Finding], cfg: Config) -> list[Finding]:
    """Suppress known/expected issues.

    Args:
        findings: List of findings
        cfg: Configuration

    Returns:
        Filtered list of findings
    """
    # TODO: Implement in Phase 1
    return findings
