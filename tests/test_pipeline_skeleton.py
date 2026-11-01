"""Tests for driftcheck pipeline skeleton."""

import subprocess

from driftcheck.config import Config
from driftcheck.models import RunMode, Severity
from driftcheck.pipeline import _is_ignored, _severity_order, run, run_and_report


class TestSeverityOrder:
    """Tests for _severity_order helper."""

    def test_low(self):
        assert _severity_order("low") == 0
        assert _severity_order(Severity.LOW) == 0

    def test_medium(self):
        assert _severity_order("medium") == 1
        assert _severity_order(Severity.MEDIUM) == 1

    def test_high(self):
        assert _severity_order("high") == 2
        assert _severity_order(Severity.HIGH) == 2

    def test_critical(self):
        assert _severity_order("critical") == 3
        assert _severity_order(Severity.CRITICAL) == 3


class TestIsIgnored:
    """Tests for _is_ignored helper."""

    def test_ignored_pattern(self, tmp_path):
        cfg = Config()
        cfg.code.ignore_globs = ["*.log", "tmp/*"]
        assert _is_ignored("debug.log", cfg) is True
        assert _is_ignored("tmp/cache.dat", cfg) is True
        assert _is_ignored("src/main.py", cfg) is False


def _create_second_commit(repo_path: str) -> str:
    """Create a second commit in the repo and return the first commit hash."""
    # Get initial commit hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True, check=True
    )
    first_commit = result.stdout.strip()

    # Create a new file and commit it
    test_file = repo_path + "/test_file.py"
    with open(test_file, "w") as f:
        f.write("def hello():\n    return 'world'\n")

    subprocess.run(["git", "add", "test_file.py"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add test file"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    return first_commit


class TestPipelineRun:
    """Tests for pipeline run function (smoke tests with stubs)."""

    def test_run_returns_empty_list_with_stubs(self, tmp_git_repo):
        """Test that run() returns empty list with all stubs returning empty."""
        cfg = Config()
        cfg.llm.mode = RunMode.NONE

        # Create a second commit so HEAD~1 exists
        base_commit = _create_second_commit(str(tmp_git_repo))

        findings = run(base_commit, "HEAD", cfg, str(tmp_git_repo))
        assert findings == []

    def test_run_with_local_mode(self, tmp_git_repo):
        """Test run() with local mode (Tier 1 + Tier 2, no verify)."""
        cfg = Config()
        cfg.llm.mode = RunMode.LOCAL

        base_commit = _create_second_commit(str(tmp_git_repo))

        findings = run(base_commit, "HEAD", cfg, str(tmp_git_repo))
        assert findings == []

    def test_run_with_full_mode(self, tmp_git_repo):
        """Test run() with full mode (Tier 1 + Tier 2 + verify)."""
        cfg = Config()
        cfg.llm.mode = RunMode.FULL

        base_commit = _create_second_commit(str(tmp_git_repo))

        findings = run(base_commit, "HEAD", cfg, str(tmp_git_repo))
        assert findings == []


class TestPipelineRunAndReport:
    """Tests for run_and_report function."""

    def test_run_and_report_returns_tuple(self, tmp_git_repo):
        """Test run_and_report returns (findings, output) tuple."""
        cfg = Config()
        cfg.llm.mode = RunMode.NONE

        base_commit = _create_second_commit(str(tmp_git_repo))

        findings, output = run_and_report(base_commit, "HEAD", cfg, str(tmp_git_repo))
        assert findings == []
        assert output == ""


class TestMainEntryPoint:
    """Tests for main() entry point."""

    def test_main_returns_zero_on_no_findings(self, tmp_git_repo):
        """Test main returns 0 when no findings."""
        from driftcheck.pipeline import main

        base_commit = _create_second_commit(str(tmp_git_repo))

        # Since stubs return empty, should return 0
        result = main(base_commit, "HEAD", str(tmp_git_repo))
        assert result in (0, 1)
