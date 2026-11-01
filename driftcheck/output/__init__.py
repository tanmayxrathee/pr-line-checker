"""Output package - formatting and reporting."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.models import ChangeFact, Finding


def format_findings(findings: list[Finding], facts: list[ChangeFact], cfg: Config) -> str:
    """Format findings for output.

    Args:
        findings: List of findings
        facts: List of change facts
        cfg: Configuration

    Returns:
        Formatted output string
    """
    # TODO: Implement in Phase 1
    return ""


def format_github_annotations(findings: list[Finding], cfg: Config) -> str:
    """Format findings as GitHub Actions annotations.

    Args:
        findings: List of findings
        cfg: Configuration

    Returns:
        Formatted annotations string
    """
    # TODO: Implement in Phase 1
    return ""
