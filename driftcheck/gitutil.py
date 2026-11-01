"""Git utilities for DriftCheck."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def run_git(args: list[str], cwd: Path | str) -> str:
    """Run a git command and return stdout.

    Args:
        args: Git command arguments (e.g., ["diff", "HEAD~1", "HEAD"])
        cwd: Working directory for the command

    Returns:
        Stdout as string, stripped of trailing newline

    Raises:
        subprocess.CalledProcessError: If the command fails
    """
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.rstrip("\n")


def merge_base(a: str, b: str, cwd: Path | str = ".") -> str:
    """Find the merge base of two commits.

    Args:
        a: First commit/ref
        b: Second commit/ref
        cwd: Repository root

    Returns:
        Merge base commit hash
    """
    return run_git(["merge-base", a, b], cwd)


def diff(
    base: str,
    head: str,
    paths: list[str] | None = None,
    unified: int = 3,
    cwd: Path | str = ".",
) -> str:
    """Generate a unified diff between two commits.

    Args:
        base: Base commit/ref
        head: Head commit/ref
        paths: Optional list of paths to limit diff to
        unified: Number of context lines (default 3)
        cwd: Repository root

    Returns:
        Unified diff as string
    """
    args = ["diff", f"--unified={unified}", "--no-color", "--find-renames", base, head]
    if paths:
        args.extend(["--", *paths])
    return run_git(args, cwd)


def changed_files(base: str, head: str, cwd: Path | str = ".") -> list[str]:
    """Get list of files changed between two commits.

    Args:
        base: Base commit/ref
        head: Head commit/ref
        cwd: Repository root

    Returns:
        List of changed file paths
    """
    output = run_git(["diff", "--name-only", base, head], cwd)
    if not output:
        return []
    return output.splitlines()


def blob_permalink_parts(cwd: Path | str = ".") -> tuple[str, str] | None:
    """Extract (owner, repo) from git remote origin URL.

    Args:
        cwd: Repository root

    Returns:
        Tuple of (owner, repo) or None if not a GitHub remote
    """
    try:
        url = run_git(["remote", "get-url", "origin"], cwd)
    except subprocess.CalledProcessError:
        return None

    # Handle SSH: git@github.com:owner/repo.git
    ssh_match = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # Handle HTTPS: https://github.com/owner/repo.git
    https_match = re.match(r"https://github\.com/([^/]+)/(.+?)(?:\.git)?$", url)
    if https_match:
        return https_match.group(1), https_match.group(2)

    return None


class RepoView:
    """View of a repository at a specific revision.

    Allows reading files and listing files at a given commit without checking out.
    """

    def __init__(self, root: Path, rev: str):
        """Initialize RepoView.

        Args:
            root: Repository root path
            rev: Git revision (commit hash, tag, branch, etc.)
        """
        self.root = Path(root).resolve()
        self.rev = rev

    def read(self, path: str) -> str | None:
        """Read a file at the given revision.

        Args:
            path: Path to file relative to repository root

        Returns:
            File contents as string, or None if file doesn't exist at that revision
        """
        try:
            return run_git(["show", f"{self.rev}:{path}"], self.root)
        except subprocess.CalledProcessError:
            return None

    def list_files(self) -> list[str]:
        """List all files in the repository at the given revision.

        Returns:
            List of file paths relative to repository root
        """
        try:
            output = run_git(["ls-tree", "-r", "--name-only", self.rev], self.root)
        except subprocess.CalledProcessError:
            return []
        if not output:
            return []
        return output.splitlines()
