"""Rename pairing for removed + added facts."""

from __future__ import annotations

import difflib

from driftcheck.models import ChangeFact, ChangeType


def _similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two strings."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def _score_rename_pair(removed: ChangeFact, added: ChangeFact) -> float:
    """Score a potential rename pair (removed -> added)."""
    score = 0.0

    # Same default
    if removed.old == added.old:
        score += 0.4

    # Same help text
    if removed.help_text and added.help_text:
        if removed.help_text == added.help_text:
            score += 0.3
        elif _similarity(removed.help_text, added.help_text) > 0.8:
            score += 0.3

    # Same type/choices
    # (This would need more context - simplified for now)
    score += 0.2

    # Same position (line distance <= 3)
    if removed.location.line_old and added.location.line_new:
        if abs(removed.location.line_old - added.location.line_new) <= 3:
            score += 0.2

    # Name similarity
    if _similarity(removed.symbol, added.symbol) > 0.5:
        score += 0.2
    elif removed.symbol in added.symbol or added.symbol in removed.symbol:
        score += 0.2

    return score


def pair_renames(facts: list[ChangeFact]) -> list[ChangeFact]:
    """Pair REMOVED and ADDED facts of the same kind into RENAMED facts.

    Args:
        facts: List of facts (may include REMOVED and ADDED)

    Returns:
        List of facts with RENAMED facts replacing paired REMOVED/ADDED
    """
    # Group by kind
    by_kind: dict[str, list[ChangeFact]] = {}
    for fact in facts:
        by_kind.setdefault(fact.kind.value, []).append(fact)

    result: list[ChangeFact] = []

    for _kind, kind_facts in by_kind.items():
        removed_facts = [f for f in kind_facts if f.change_type == ChangeType.REMOVED]
        added_facts = [f for f in kind_facts if f.change_type == ChangeType.ADDED]
        other_facts = [
            f for f in kind_facts if f.change_type not in (ChangeType.REMOVED, ChangeType.ADDED)
        ]

        # Add non-removed/added facts directly
        result.extend(other_facts)

        # Pair removed and added
        paired_removed: set[int] = set()
        paired_added: set[int] = set()

        for i, removed in enumerate(removed_facts):
            best_score = 0.0
            best_j = -1

            for j, added in enumerate(added_facts):
                if j in paired_added:
                    continue
                score = _score_rename_pair(removed, added)
                if score > best_score and score >= 0.5:
                    best_score = score
                    best_j = j

            if best_j >= 0:
                added = added_facts[best_j]
                paired_removed.add(i)
                paired_added.add(best_j)

                # Create RENAMED fact
                renamed_fact = ChangeFact(
                    id=removed.id,  # will be reassigned later
                    symbol=added.symbol,
                    kind=removed.kind,
                    change_type=ChangeType.RENAMED,
                    old=removed.symbol,
                    new=added.symbol,
                    aliases=[],
                    location=removed.location,
                    code_snippet=removed.code_snippet,
                    help_text=added.help_text,
                    extractor=removed.extractor,
                    public=removed.public,
                    related=[removed.id, added.id],
                )
                result.append(renamed_fact)

                # If defaults also differ, create a DEFAULT_CHANGED fact
                if removed.old != added.old:
                    default_fact = ChangeFact(
                        id=removed.id,  # will be reassigned later
                        symbol=added.symbol,
                        kind=added.kind,
                        change_type=ChangeType.DEFAULT_CHANGED,
                        old=removed.old,
                        new=added.old,
                        aliases=[],
                        location=added.location,
                        code_snippet=added.code_snippet,
                        help_text=added.help_text,
                        extractor=added.extractor,
                        public=added.public,
                        related=[renamed_fact.id],
                    )
                    result.append(default_fact)

        # Add unpaired REMOVED and ADDED facts
        for i, fact in enumerate(removed_facts):
            if i not in paired_removed:
                result.append(fact)

        for j, fact in enumerate(added_facts):
            if j not in paired_added:
                result.append(fact)

    return result
