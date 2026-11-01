"""Extract package - code change fact extraction."""

from __future__ import annotations

from driftcheck.config import Config
from driftcheck.extract.base import Extractor, should_extract
from driftcheck.extract.diffparse import parse_diff
from driftcheck.extract.gate import apply_gate
from driftcheck.extract.rename import pair_renames
from driftcheck.gitutil import RepoView
from driftcheck.models import ChangeFact


def extract_facts(diff_text: str, repo: RepoView, cfg: Config) -> list[ChangeFact]:
    """Extract code change facts from a unified diff.

    Args:
        diff_text: Unified diff text
        repo: Repository view for reading files at revisions
        cfg: Configuration

    Returns:
        List of ChangeFact objects with assigned F# IDs
    """
    file_changes = parse_diff(diff_text)
    all_facts: list[ChangeFact] = []

    for fc in file_changes:
        if not should_extract(fc.path, cfg):
            continue

        # Fetch old and new source
        old_src = None if fc.status == "added" else repo.read(fc.old_path)
        new_src = None if fc.status == "removed" else repo.read(fc.new_path)

        # Run extractors (imported dynamically to avoid circular imports)
        from driftcheck.extract.config_files import ConfigFilesExtractor
        from driftcheck.extract.generic_regex import GenericRegexExtractor
        from driftcheck.extract.py_cli import CLIExtractor
        from driftcheck.extract.py_env import EnvExtractor
        from driftcheck.extract.py_models import ModelsExtractor
        from driftcheck.extract.py_symbols import SymbolsExtractor

        extractors: list[Extractor] = [
            CLIExtractor(),
            SymbolsExtractor(),
            EnvExtractor(),
            ModelsExtractor(),
            ConfigFilesExtractor(),
            GenericRegexExtractor(),
        ]

        for extractor in extractors:
            if extractor.applies_to(fc.path):
                facts = extractor.extract(fc, old_src, new_src)
                all_facts.extend(facts)

    # Pair renames
    all_facts = pair_renames(all_facts)

    # Apply gate
    all_facts = apply_gate(all_facts, cfg)

    # Deduplicate identical facts
    all_facts = _deduplicate_facts(all_facts)

    # Assign F# IDs in file/line order
    all_facts = _assign_ids(all_facts)

    return all_facts


def _deduplicate_facts(facts: list[ChangeFact]) -> list[ChangeFact]:
    """Remove duplicate facts (same symbol, kind, change_type, old, new, location)."""
    seen: set[tuple] = set()
    unique: list[ChangeFact] = []

    for fact in facts:
        key = (
            fact.symbol,
            fact.kind,
            fact.change_type,
            fact.old,
            fact.new,
            fact.location.path,
            fact.location.line_old,
            fact.location.line_new,
        )
        if key not in seen:
            seen.add(key)
            unique.append(fact)

    return unique


def _assign_ids(facts: list[ChangeFact]) -> list[ChangeFact]:
    """Assign F# IDs in file/line order."""
    # Sort by file path, then line_old, then line_new
    sorted_facts = sorted(
        facts,
        key=lambda f: (
            f.location.path,
            f.location.line_old or 0,
            f.location.line_new or 0,
        ),
    )

    for i, fact in enumerate(sorted_facts, 1):
        fact.id = f"F{i}"

    return sorted_facts
