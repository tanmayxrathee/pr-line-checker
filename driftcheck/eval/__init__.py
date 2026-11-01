"""Eval package - evaluation harness."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.models import ChangeFact, Finding


def evaluate(
    findings: list[Finding],
    facts: list[ChangeFact],
    ground_truth: list[Finding],
    cfg: Config,
) -> dict[str, float]:
    """Evaluate findings against ground truth.

    Args:
        findings: List of detected findings
        facts: List of change facts
        ground_truth: List of expected findings
        cfg: Configuration

    Returns:
        Dictionary of metrics (precision, recall, f1, etc.)
    """
    # TODO: Implement in Phase 3
    return {
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
    }
