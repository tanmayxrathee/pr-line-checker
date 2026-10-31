"""Tests for guard scripts."""

import subprocess

COMMIT_WITH_TRAILERS = (
    "Add test file\n\n"
    "Coding agent: Test Agent\n"
    "Models used in project: Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)"
)


class TestCheckHackathonMd:
    """Tests for check_hackathon_md.py."""

    def test_hackathon_unchanged(self, tmp_git_repo, project_root):
        """Test that unchanged HACKATHON.md passes."""
        script_path = project_root / "scripts" / "check_hackathon_md.py"
        result = subprocess.run(
            ["python", str(script_path)],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "OK: HACKATHON.md is unchanged" in result.stdout

    def test_hackathon_modified(self, tmp_git_repo, project_root):
        """Test that modified HACKATHON.md fails."""
        # Modify HACKATHON.md
        hackathon_path = tmp_git_repo / "HACKATHON.md"
        hackathon_path.write_text("# Modified HACKATHON\n\nThis has been changed.\n")
        subprocess.run(["git", "add", "HACKATHON.md"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Modify HACKATHON.md"], cwd=tmp_git_repo, check=True)

        script_path = project_root / "scripts" / "check_hackathon_md.py"
        result = subprocess.run(
            ["python", str(script_path)],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "ERROR: HACKATHON.md has been modified" in result.stderr


class TestCheckCommitTrailers:
    """Tests for check_commit_trailers.py."""

    def test_commits_with_trailers_pass(self, tmp_git_repo, project_root):
        """Test that commits with proper trailers pass."""
        # Add a commit with proper trailers
        test_file = tmp_git_repo / "test.txt"
        test_file.write_text("test\n")
        subprocess.run(["git", "add", "test.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", COMMIT_WITH_TRAILERS],
            cwd=tmp_git_repo,
            check=True,
        )

        script_path = project_root / "scripts" / "check_commit_trailers.py"
        result = subprocess.run(
            ["python", str(script_path)],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "OK: All 1 commits have required trailers" in result.stdout

    def test_commits_without_trailers_fail(self, tmp_git_repo, project_root):
        """Test that commits without trailers fail."""
        # Add a commit without trailers
        test_file = tmp_git_repo / "test.txt"
        test_file.write_text("test\n")
        subprocess.run(["git", "add", "test.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add test file without trailers"],
            cwd=tmp_git_repo,
            check=True,
        )

        script_path = project_root / "scripts" / "check_commit_trailers.py"
        result = subprocess.run(
            ["python", str(script_path)],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "ERROR: Commits missing required trailers" in result.stderr
        assert "Coding agent:" in result.stderr
        assert "Models used in project:" in result.stderr

    def test_partial_trailers_fail(self, tmp_git_repo, project_root):
        """Test that commits with only one trailer fail."""
        # Add a commit with only Coding agent
        test_file = tmp_git_repo / "test.txt"
        test_file.write_text("test\n")
        subprocess.run(["git", "add", "test.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add test file\n\nCoding agent: Test Agent"],
            cwd=tmp_git_repo,
            check=True,
        )

        script_path = project_root / "scripts" / "check_commit_trailers.py"
        result = subprocess.run(
            ["python", str(script_path)],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Models used in project:" in result.stderr
