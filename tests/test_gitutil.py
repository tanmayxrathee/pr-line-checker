"""Tests for driftcheck git utilities."""

import subprocess

import pytest

from driftcheck.gitutil import (
    RepoView,
    blob_permalink_parts,
    changed_files,
    diff,
    merge_base,
    run_git,
)


class TestRunGit:
    """Tests for run_git function."""

    def test_basic_command(self, tmp_git_repo):
        """Test running a basic git command."""
        result = run_git(["rev-parse", "HEAD"], tmp_git_repo)
        assert len(result) == 40  # SHA1 hash

    def test_command_fails(self, tmp_git_repo):
        """Test that failed command raises CalledProcessError."""
        with pytest.raises(subprocess.CalledProcessError):
            run_git(["invalid-command"], tmp_git_repo)


class TestMergeBase:
    """Tests for merge_base function."""

    def test_merge_base_two_branches(self, tmp_git_repo):
        """Test finding merge base of two branches."""
        # Create a feature branch
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_git_repo, check=True)
        feature_file = tmp_git_repo / "feature.txt"
        feature_file.write_text("feature\n")
        subprocess.run(["git", "add", "feature.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add feature"], cwd=tmp_git_repo, check=True)

        # Go back to main and make a commit
        subprocess.run(["git", "checkout", "master"], cwd=tmp_git_repo, check=True)
        main_file = tmp_git_repo / "main.txt"
        main_file.write_text("main\n")
        subprocess.run(["git", "add", "main.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add main"], cwd=tmp_git_repo, check=True)

        # Merge base should be the initial commit
        base = merge_base("master", "feature", tmp_git_repo)
        assert len(base) == 40


class TestDiff:
    """Tests for diff function."""

    def test_diff_between_commits(self, tmp_git_repo):
        """Test generating diff between two commits."""
        # Create first commit
        file1 = tmp_git_repo / "file1.txt"
        file1.write_text("line 1\nline 2\nline 3\n")
        subprocess.run(["git", "add", "file1.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "First commit"], cwd=tmp_git_repo, check=True)
        first_commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        # Create second commit with changes
        file1.write_text("line 1\nline 2 modified\nline 3\nline 4\n")
        subprocess.run(["git", "add", "file1.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Second commit"], cwd=tmp_git_repo, check=True)
        second_commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        # Generate diff
        diff_output = diff(first_commit, second_commit, cwd=tmp_git_repo)

        assert "line 2 modified" in diff_output
        assert "line 4" in diff_output
        assert "--- a/file1.txt" in diff_output
        assert "+++ b/file1.txt" in diff_output

    def test_diff_with_paths(self, tmp_git_repo):
        """Test diff with path filtering."""
        # Create two files
        file1 = tmp_git_repo / "file1.txt"
        file1.write_text("content 1\n")
        file2 = tmp_git_repo / "file2.txt"
        file2.write_text("content 2\n")
        subprocess.run(["git", "add", "file1.txt", "file2.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add two files"], cwd=tmp_git_repo, check=True)
        first_commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        # Modify only file1
        file1.write_text("content 1 modified\n")
        subprocess.run(["git", "add", "file1.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Modify file1"], cwd=tmp_git_repo, check=True)
        second_commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        # Diff only file1
        diff_output = diff(first_commit, second_commit, paths=["file1.txt"], cwd=tmp_git_repo)
        assert "file1.txt" in diff_output
        assert "file2.txt" not in diff_output


class TestChangedFiles:
    """Tests for changed_files function."""

    def test_changed_files(self, tmp_git_repo):
        """Test getting list of changed files."""
        # Create first commit
        file1 = tmp_git_repo / "file1.txt"
        file1.write_text("content\n")
        subprocess.run(["git", "add", "file1.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "First"], cwd=tmp_git_repo, check=True)
        first_commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        # Create second commit with new file and modified file
        file1.write_text("modified\n")
        file2 = tmp_git_repo / "file2.txt"
        file2.write_text("new\n")
        subprocess.run(["git", "add", "file1.txt", "file2.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Second"], cwd=tmp_git_repo, check=True)
        second_commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        changed = changed_files(first_commit, second_commit, cwd=tmp_git_repo)
        assert set(changed) == {"file1.txt", "file2.txt"}


class TestBlobPermalinkParts:
    """Tests for blob_permalink_parts function."""

    def _add_origin_remote(self, tmp_git_repo, url: str):
        """Helper to add origin remote with given URL."""
        subprocess.run(["git", "remote", "add", "origin", url], cwd=tmp_git_repo, check=True)

    def test_no_remote(self, tmp_git_repo):
        """Test returns None when no origin remote."""
        # Remove origin remote if it exists
        subprocess.run(
            ["git", "remote", "remove", "origin"],
            cwd=tmp_git_repo,
            check=False,
            capture_output=True,
        )
        result = blob_permalink_parts(tmp_git_repo)
        assert result is None

    def test_https_github_url(self, tmp_git_repo):
        """Test parsing HTTPS GitHub URL."""
        self._add_origin_remote(tmp_git_repo, "https://github.com/owner/repo.git")
        result = blob_permalink_parts(tmp_git_repo)
        assert result == ("owner", "repo")

    def test_ssh_github_url(self, tmp_git_repo):
        """Test parsing SSH GitHub URL."""
        self._add_origin_remote(tmp_git_repo, "git@github.com:owner/repo.git")
        result = blob_permalink_parts(tmp_git_repo)
        assert result == ("owner", "repo")

    def test_non_github_url(self, tmp_git_repo):
        """Test returns None for non-GitHub URLs."""
        self._add_origin_remote(tmp_git_repo, "https://gitlab.com/owner/repo.git")
        result = blob_permalink_parts(tmp_git_repo)
        assert result is None


class TestRepoView:
    """Tests for RepoView class."""

    def test_read_existing_file(self, tmp_git_repo):
        """Test reading an existing file at a revision."""
        # Create a file and commit
        test_file = tmp_git_repo / "test.txt"
        test_file.write_text("Hello, World!\n")
        subprocess.run(["git", "add", "test.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add test file"], cwd=tmp_git_repo, check=True)
        commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        # Read file at that commit (git show doesn't include trailing newline)
        repo_view = RepoView(tmp_git_repo, commit)
        content = repo_view.read("test.txt")

        assert content == "Hello, World!"

    def test_read_missing_file(self, tmp_git_repo):
        """Test reading a non-existent file returns None."""
        # Create a commit
        test_file = tmp_git_repo / "test.txt"
        test_file.write_text("Hello\n")
        subprocess.run(["git", "add", "test.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add test file"], cwd=tmp_git_repo, check=True)
        commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        # Try to read non-existent file
        repo_view = RepoView(tmp_git_repo, commit)
        content = repo_view.read("nonexistent.txt")

        assert content is None

    def test_read_file_at_different_revisions(self, tmp_git_repo):
        """Test reading the same file at different revisions."""
        # First commit
        test_file = tmp_git_repo / "test.txt"
        test_file.write_text("Version 1\n")
        subprocess.run(["git", "add", "test.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Version 1"], cwd=tmp_git_repo, check=True)
        commit1 = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        # Second commit - modify file
        test_file.write_text("Version 2\n")
        subprocess.run(["git", "add", "test.txt"], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Version 2"], cwd=tmp_git_repo, check=True)
        commit2 = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        # Read at both revisions (git show doesn't include trailing newline)
        repo_view1 = RepoView(tmp_git_repo, commit1)
        repo_view2 = RepoView(tmp_git_repo, commit2)

        assert repo_view1.read("test.txt") == "Version 1"
        assert repo_view2.read("test.txt") == "Version 2"

    def test_list_files(self, tmp_git_repo):
        """Test listing files at a revision."""
        # Create multiple files
        (tmp_git_repo / "file1.txt").write_text("1\n")
        (tmp_git_repo / "file2.txt").write_text("2\n")
        (tmp_git_repo / "dir").mkdir(exist_ok=True)
        (tmp_git_repo / "dir" / "file3.txt").write_text("3\n")

        subprocess.run(["git", "add", "."], cwd=tmp_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add files"], cwd=tmp_git_repo, check=True)
        commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        repo_view = RepoView(tmp_git_repo, commit)
        files = repo_view.list_files()

        # Fixture already has HACKATHON.md in initial commit
        assert set(files) == {"file1.txt", "file2.txt", "dir/file3.txt", "HACKATHON.md"}

    def test_list_files_empty_repo(self, tmp_git_repo):
        """Test listing files in repo with only initial commit."""
        # The fixture already has HACKATHON.md in initial commit
        commit = run_git(["rev-parse", "HEAD"], tmp_git_repo)

        repo_view = RepoView(tmp_git_repo, commit)
        files = repo_view.list_files()

        assert "HACKATHON.md" in files
