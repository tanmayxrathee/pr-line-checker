"""Pipeline orchestration for DriftCheck."""

from __future__ import annotations

from pathlib import Path

from driftcheck.config import Config
from driftcheck.docs import extract_doc_facts

# Import stage functions
from driftcheck.extract import extract_facts
from driftcheck.filters import deduplicate_findings, suppress_known_issues
from driftcheck.github import post_annotations, post_pr_comment
from driftcheck.gitutil import RepoView, changed_files, diff, merge_base
from driftcheck.llm import analyze_tier2, verify_findings
from driftcheck.models import ChangeFact, Finding, RunMode, Severity
from driftcheck.output import format_findings
from driftcheck.search import retrieve_candidates
from driftcheck.tier1 import detect_tier1


def run(
    base_ref: str,
    head_ref: str,
    cfg: Config,
    repo_root: str = ".",
) -> list[Finding]:
    """Run the full DriftCheck pipeline.

    Args:
        base_ref: Base git reference (e.g., main, HEAD~1)
        head_ref: Head git reference (e.g., HEAD, feature-branch)
        cfg: Configuration
        repo_root: Path to repository root

    Returns:
        List of all findings
    """
    repo = RepoView(Path(repo_root), head_ref)

    # 1. Find merge base and get changed files
    base = merge_base(base_ref, head_ref, repo_root)
    changed = changed_files(base, head_ref, repo_root)

    # Filter out ignored files per config
    changed = [f for f in changed if not _is_ignored(f, cfg)]

    # 2. Get unified diff for all changed files
    diff_text = diff(base, head_ref, paths=changed, cwd=repo_root)

    # 3. Extract code change facts
    facts = extract_facts(diff_text, repo, cfg)

    # 4. Extract documentation facts from repo at head_ref
    doc_facts = extract_doc_facts(repo, cfg)

    # 5. Retrieve candidates for each fact via BM25
    fact_candidates = retrieve_candidates(facts, doc_facts, cfg)

    all_findings: list[Finding] = []

    # 6. Run Tier 1 (deterministic) for all facts
    for fact, candidates in fact_candidates:
        tier1_findings = detect_tier1(fact, candidates, cfg)
        all_findings.extend(tier1_findings)

    # 7. Run Tier 2 based on mode
    if cfg.llm.mode != RunMode.NONE:
        for fact, candidates in fact_candidates:
            tier2_findings = analyze_tier2(fact, candidates, cfg)
            all_findings.extend(tier2_findings)

    # 8. Run verification (Tier 3) if mode is FULL
    if cfg.llm.mode == RunMode.FULL:
        # Group findings by fact for verification
        findings_by_fact: dict[str, list[Finding]] = {}
        for finding in all_findings:
            findings_by_fact.setdefault(finding.fact.id, []).append(finding)

        for fact, candidates in fact_candidates:
            fact_findings = findings_by_fact.get(fact.id, [])
            if fact_findings:
                verified = verify_findings(fact_findings, fact, candidates, cfg)
                # Replace unverified with verified
                all_findings = [f for f in all_findings if f.fact.id != fact.id]
                all_findings.extend(verified)

    # 9. Deduplicate and suppress known issues
    all_findings = deduplicate_findings(all_findings, cfg)
    all_findings = suppress_known_issues(all_findings, cfg)

    # 10. Filter by fail_on severity
    min_severity = _severity_order(cfg.general.fail_on)
    all_findings = [f for f in all_findings if _severity_order(f.severity) >= min_severity]

    return all_findings


def run_and_report(
    base_ref: str,
    head_ref: str,
    cfg: Config,
    repo_root: str = ".",
) -> tuple[list[Finding], str]:
    """Run pipeline and format output.

    Args:
        base_ref: Base git reference
        head_ref: Head git reference
        cfg: Configuration
        repo_root: Path to repository root

    Returns:
        Tuple of (findings, formatted_output)
    """
    facts: list[ChangeFact] = []
    repo = RepoView(Path(repo_root), head_ref)

    base = merge_base(base_ref, head_ref, repo_root)
    changed = changed_files(base, head_ref, repo_root)
    changed = [f for f in changed if not _is_ignored(f, cfg)]
    diff_text = diff(base, head_ref, paths=changed, cwd=repo_root)
    facts = extract_facts(diff_text, repo, cfg)

    findings = run(base_ref, head_ref, cfg, repo_root)
    output = format_findings(findings, facts, cfg)

    return findings, output


def _is_ignored(file_path: str, cfg: Config) -> bool:
    """Check if a file should be ignored based on config patterns."""
    from fnmatch import fnmatch

    for pattern in cfg.code.ignore_globs:
        if fnmatch(file_path, pattern):
            return True
    return False


def _severity_order(severity: Severity | str) -> int:
    """Convert severity to numeric order for comparison."""
    if isinstance(severity, str):
        severity = Severity(severity)
    order = {
        Severity.LOW: 0,
        Severity.MEDIUM: 1,
        Severity.HIGH: 2,
        Severity.CRITICAL: 3,
    }
    return order.get(severity, 0)


def main(
    base_ref: str,
    head_ref: str,
    repo_root: str = ".",
    cfg: Config | None = None,
) -> int:
    """CLI entry point for pipeline (used by __main__.py).

    Args:
        base_ref: Base git reference
        head_ref: Head git reference
        repo_root: Path to repository root
        cfg: Optional config (will be loaded if not provided)

    Returns:
        Exit code (0 = pass, 1 = fail)
    """
    from driftcheck.config import load_config

    if cfg is None:
        cfg = load_config(repo_root)

    findings, output = run_and_report(base_ref, head_ref, cfg, repo_root)

    # Print formatted output
    if output:
        print(output)  # noqa: T201

    # Post to GitHub if configured
    if cfg.general.report_gaps:
        post_pr_comment(findings, cfg)
        post_annotations(findings, cfg)

    # Determine exit code based on fail_on
    min_severity = _severity_order(cfg.general.fail_on)
    has_fail = any(_severity_order(f.severity) >= min_severity for f in findings)

    return 1 if has_fail else 0
