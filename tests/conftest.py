"""Pytest configuration and fixtures."""

import subprocess
from pathlib import Path

import pytest

INITIAL_COMMIT_MSG = (
    "Initial commit with HACKATHON.md\n\n"
    "Coding agent: Test Agent\n"
    "Models used in project: Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)"
)


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a temporary git repository for testing with HACKATHON.md in initial commit."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Get project root (where HACKATHON.md and scripts are)
    project_root = Path(__file__).parent.parent

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Copy HACKATHON.md to repo and make initial commit
    hackathon_src = project_root / "HACKATHON.md"
    hackathon_dst = repo / "HACKATHON.md"
    hackathon_dst.write_text(hackathon_src.read_text())

    subprocess.run(["git", "add", "HACKATHON.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", INITIAL_COMMIT_MSG],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return repo


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent
