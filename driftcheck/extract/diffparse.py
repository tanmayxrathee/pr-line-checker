"""Diff parsing using unidiff."""

from __future__ import annotations

from unidiff import PatchSet

from driftcheck.extract.base import FileChange, Hunk


def _strip_prefix(path: str) -> str:
    """Strip a/ or b/ prefix from git diff paths."""
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def parse_diff(text: str) -> list[FileChange]:
    """Parse a unified diff text into a list of FileChange objects.

    Args:
        text: Unified diff text

    Returns:
        List of FileChange objects
    """
    if not text.strip():
        return []

    patch_set = PatchSet(text.splitlines(keepends=True))
    file_changes: list[FileChange] = []

    for patched_file in patch_set:
        # Determine status
        if patched_file.is_added_file:
            status = "added"
        elif patched_file.is_removed_file:
            status = "removed"
        elif patched_file.is_rename:
            status = "renamed"
        else:
            status = "modified"

        # Get old_path and new_path
        if patched_file.is_added_file:
            old_path = "/dev/null"
            new_path = _strip_prefix(patched_file.target_file)
        elif patched_file.is_removed_file:
            old_path = _strip_prefix(patched_file.source_file)
            new_path = "/dev/null"
        elif patched_file.is_rename:
            old_path = _strip_prefix(patched_file.source_file)
            new_path = _strip_prefix(patched_file.target_file)
        else:
            old_path = _strip_prefix(patched_file.source_file)
            new_path = _strip_prefix(patched_file.target_file)

        hunks: list[Hunk] = []
        for hunk in patched_file:
            lines: list[tuple[str, int | None, int | None, str]] = []
            for line in hunk:
                tag = " "  # context
                if line.is_added:
                    tag = "+"
                elif line.is_removed:
                    tag = "-"
                elif line.line_type == "\\":
                    tag = "\\"

                lines.append(
                    (
                        tag,
                        line.source_line_no,
                        line.target_line_no,
                        line.value.rstrip("\n"),
                    )
                )

            hunks.append(
                Hunk(
                    old_start=hunk.source_start,
                    old_len=hunk.source_length,
                    new_start=hunk.target_start,
                    new_len=hunk.target_length,
                    lines=lines,
                )
            )

        file_changes.append(
            FileChange(
                old_path=old_path,
                new_path=new_path,
                status=status,
                hunks=hunks,
            )
        )

    return file_changes
