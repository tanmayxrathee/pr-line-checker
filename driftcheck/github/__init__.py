"""GitHub package - GitHub Actions integration."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.models import Finding


def post_pr_comment(findings: list[Finding], cfg: Config) -> None:
    """Post findings as a PR comment.

    Args:
        findings: List of findings
        cfg: Configuration
    """
    # TODO: Implement in Phase 2
    pass


def post_annotations(findings: list[Finding], cfg: Config) -> None:
    """Post findings as GitHub Actions annotations.

    Args:
        findings: List of findings
        cfg: Configuration
    """
    # TODO: Implement in Phase 2
    pass
