#!/usr/bin/env python3
"""Check that HACKATHON.md has not been modified since the initial commit."""

import subprocess
import sys


def run_git(*args: str) -> str:
    """Run git command and return stdout."""
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def main() -> int:
    try:
        # Find the root commit (initial commit)
        root_commit = run_git("rev-list", "--max-parents=0", "HEAD")
        if not root_commit:
            print("ERROR: Could not find root commit", file=sys.stderr)
            return 1

        # Get the blob hash of HACKATHON.md at root commit
        root_hash = run_git("ls-tree", root_commit, "HACKATHON.md")
        if not root_hash:
            print("ERROR: HACKATHON.md not found in root commit", file=sys.stderr)
            return 1

        # Extract the blob hash (format: "100644 blob <hash>\tHACKATHON.md")
        root_blob_hash = root_hash.split()[2]

        # Get the blob hash of HACKATHON.md at HEAD
        head_hash = run_git("ls-tree", "HEAD", "HACKATHON.md")
        if not head_hash:
            print("ERROR: HACKATHON.md not found at HEAD", file=sys.stderr)
            return 1

        head_blob_hash = head_hash.split()[2]

        # Compare
        if root_blob_hash != head_blob_hash:
            print(
                "ERROR: HACKATHON.md has been modified!\n"
                f"  Root commit blob hash: {root_blob_hash}\n"
                f"  HEAD blob hash:        {head_blob_hash}\n"
                "  HACKATHON.md must never be modified. Please revert any changes.",
                file=sys.stderr,
            )
            return 1

        print("OK: HACKATHON.md is unchanged from root commit")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Git command failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())