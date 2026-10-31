"""Smoke tests for driftcheck CLI."""

from typer.testing import CliRunner

from driftcheck.cli import app


def test_version() -> None:
    """Test that --version works."""
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "driftcheck 0.1.0" in result.output


def test_help() -> None:
    """Test that --help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Automated Documentation Drift Detection" in result.output


def test_check_help() -> None:
    """Test that check subcommand help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["check", "--help"])
    assert result.exit_code == 0
    assert "Check for documentation drift" in result.output


def test_replay_help() -> None:
    """Test that replay subcommand help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["replay", "--help"])
    assert result.exit_code == 0
    assert "Replay drift check" in result.output


def test_mine_help() -> None:
    """Test that mine subcommand help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["mine", "--help"])
    assert result.exit_code == 0
    assert "Mine labelled drift cases" in result.output


def test_eval_help() -> None:
    """Test that eval subcommand help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    assert "Evaluate drift detection" in result.output


def test_hook_help() -> None:
    """Test that hook subcommand help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["hook", "--help"])
    assert result.exit_code == 0
    assert "Manage git pre-push hook" in result.output


def test_ignore_help() -> None:
    """Test that ignore subcommand help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["ignore", "--help"])
    assert result.exit_code == 0
    assert "Dismiss a finding" in result.output


def test_github_help() -> None:
    """Test that github subcommand help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["github", "--help"])
    assert result.exit_code == 0
    assert "Run as GitHub Action" in result.output


def test_doctor_help() -> None:
    """Test that doctor subcommand help works."""
    runner = CliRunner()
    result = runner.invoke(app, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "Check environment" in result.output
