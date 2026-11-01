#!/usr/bin/env python3
"""Check that commit messages contain required trailers."""

import subprocess
import sys
import re


def run_git(*args: str) -> str:
    """Run git command and return stdout."""
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def main() -> int:
    try:
        # Get the range of commits to check: origin/main..HEAD (PR range)
        # If origin/main doesn't exist, fall back to checking all commits
        try:
            base = run_git("merge-base", "origin/main", "HEAD")
            commit_range = f"{base}..HEAD"
        except subprocess.CalledProcessError:
            # No origin/main, check all commits from root
            root_commit = run_git("rev-list", "--max-parents=0", "HEAD")
            commit_range = f"{root_commit}..HEAD"

        # Get commit hashes in range
        commits_output = run_git("rev-list", "--reverse", commit_range)
        if not commits_output:
            print("No commits to check")
            return 0

        commits = commits_output.splitlines()

        missing_trailers = []
        for commit in commits:
            # Get commit message
            message = run_git("log", "--format=%B", "-n", "1", commit)

            # Check for required trailers
            has_coding_agent = "Coding agent:" in message
            has_models = "Models used in project:" in message

            if not has_coding_agent or not has_models:
                missing_trailers.append({
                    "commit": commit[:8],
                    "has_coding_agent": has_coding_agent,
                    "has_models": has_models,
                })

        if missing_trailers:
            print("ERROR: Commits missing required trailers:", file=sys.stderr)
            for item in missing_trailers:
                missing = []
                if not item["has_coding_agent"]:
                    missing.append("Coding agent:")
                if not item["has_models"]:
                    missing.append("Models used in project:")
                print(f"  {item['commit']}: missing {', '.join(missing)}", file=sys.stderr)
            print(
                "\nEach commit message must end with:\n"
                "  Coding agent: <your agent name and model>\n"
                "  Models used in project: Qwen3-4B (local), Nemotron-3-Ultra-550B (NVIDIA NIM)",
                file=sys.stderr,
            )
            return 1

        print(f"OK: All {len(commits)} commits have required trailers")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Git command failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())