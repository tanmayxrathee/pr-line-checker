"""DriftCheck data models (contracts).

These models are the API between phases. They are FROZEN after Phase 0.
Nobody changes them without a "contract change" PR approved by the human lead.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum

from pydantic import BaseModel


def _normalize(text: str) -> str:
    """Normalize text for fingerprint: lowercase, collapse whitespace, strip punctuation at ends."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .,;:!?")
    return text


class SymbolKind(StrEnum):
    """Kind of symbol that changed."""

    CLI_FLAG = "cli_flag"  # --timeout, -t, subcommand names
    ENV_VAR = "env_var"  # APP_TIMEOUT
    CONFIG_KEY = "config_key"  # server.timeout (dotted path)
    FUNCTION = "function"  # module.func
    CLASS = "class"
    PARAMETER = "parameter"  # func(param)
    CONSTANT = "constant"  # MAX_RETRIES = 3
    FIELD = "field"  # dataclass / pydantic field
    CHOICE = "choice"  # enum / choices=[...] value
    ENDPOINT = "endpoint"  # "/api/v1/users" (regex fallback)


class ChangeType(StrEnum):
    """Type of change detected."""

    ADDED = "added"
    REMOVED = "removed"
    RENAMED = "renamed"
    DEFAULT_CHANGED = "default_changed"
    TYPE_CHANGED = "type_changed"
    CHOICES_CHANGED = "choices_changed"
    SIGNATURE_CHANGED = "signature_changed"
    BEHAVIOR_CHANGED = "behavior_changed"  # body changed, public symbol (Tier 2 only)


class CodeLocation(BaseModel):
    """Location of code change."""

    path: str
    line_old: int | None = None  # line in base version (for removed lines)
    line_new: int | None = None  # line in head version
    commit: str | None = None


class ChangeFact(BaseModel):
    """A single extracted fact about a code change."""

    id: str  # "F1", "F2"… assigned by pipeline in order
    symbol: str  # canonical name, e.g. "--request-timeout"
    kind: SymbolKind
    change_type: ChangeType
    old: str | None = None  # old name/value/signature (string form)
    new: str | None = None
    aliases: list[str] = []  # other spellings that may appear in docs
    location: CodeLocation
    code_snippet: str = ""  # the relevant diff lines (± and context), ≤ 20 lines
    help_text: str | None = None  # argparse help=, docstring first line, field description
    extractor: str  # which extractor produced it, e.g. "py_cli"
    public: bool = True  # gate result: does it plausibly affect users?
    related: list[str] = []  # other fact IDs (e.g. rename ↔ default change)


class BlockType(StrEnum):
    """Type of documentation block."""

    PROSE = "prose"
    LIST_ITEM = "list_item"
    TABLE_ROW = "table_row"
    HEADING = "heading"
    CODE = "code"  # one line inside a fenced/literal block
    ADMONITION = "admonition"


class DocSentence(BaseModel):
    """A single sentence/unit from documentation."""

    id: str  # "S1".. unique per run
    path: str
    line_start: int
    line_end: int
    text: str  # raw text as in the file (markup kept)
    plain: str  # markup stripped, for BM25
    block: BlockType
    heading_path: list[str] = []  # ["Usage", "Options"]
    code_spans: list[str] = []  # contents of `inline code`
    ignored: bool = False  # inside a drift-ignore region


class MatchType(StrEnum):
    """How a candidate sentence matched a fact."""

    EXACT_OLD = "exact_old"  # sentence contains fact.old
    EXACT_SYMBOL = "exact_symbol"  # contains fact.symbol or an alias
    BM25 = "bm25"
    LINK = "link"  # indirect (call graph, docstring, same section)


class Candidate(BaseModel):
    """A candidate sentence that might discuss a fact."""

    fact_id: str
    sentence_id: str
    match: MatchType
    score: float  # 0..1 normalised
    matched_token: str | None = None


class Tier(StrEnum):
    """Detection tier."""

    HARD = "tier1"
    SOFT = "tier2"


class Severity(StrEnum):
    """Finding severity."""

    CRITICAL = "critical"  # docs tell users to run something that no longer exists
    HIGH = "high"  # wrong default / renamed param
    MEDIUM = "medium"  # type/choices/signature mismatch
    LOW = "low"  # prose/behaviour mismatch
    INFO = "info"  # doc gap (new public thing undocumented)


class Verification(BaseModel):
    """Verification result from Nemotron or self-check."""

    by: str  # "nemotron-3-ultra", "qwen-selfcheck", "none"
    decision: str  # "confirm" | "reject" | "revise" | "skipped"
    confidence: float
    reason: str = ""


class Finding(BaseModel):
    """A documentation drift finding."""

    id: str  # "D1".. (D for drift)
    fingerprint: str  # stable hash, see §3.1
    tier: Tier
    rule: str  # "R1_removed_flag" … or "T2_prose"
    severity: Severity
    confidence: float  # 1.0 for Tier 1
    fact: ChangeFact
    sentence: DocSentence
    doc_quote: str  # literal substring of sentence.text
    code_quote: str  # literal substring of fact.code_snippet
    message: str  # one-line human explanation
    suggested_text: str | None = None  # full corrected sentence
    verification: Verification | None = None
    suppressed_by: str | None = None  # filter name if filtered (kept for debug/eval)

    @classmethod
    def compute_fingerprint(
        cls,
        rule: str,
        kind: SymbolKind,
        symbol: str,
        old: str | None,
        sentence_plain: str,
    ) -> str:
        """Compute stable fingerprint for a finding.

        fingerprint = sha1(f"{rule}|{kind}|{symbol}|{old}|{normalize(plain)}").hexdigest()[:16]
        """
        old_str = old or ""
        data = f"{rule}|{kind.value}|{symbol}|{old_str}|{_normalize(sentence_plain)}"
        return hashlib.sha1(data.encode()).hexdigest()[:16]


class RunMode(StrEnum):
    """LLM run mode."""

    NONE = "none"  # Tier 1 only
    LOCAL = "local"  # Tier 1 + Qwen + Qwen self-check
    FULL = "full"  # Tier 1 + Qwen + Nemotron verify


class RunReport(BaseModel):
    """Complete report from a driftcheck run."""

    tool_version: str
    mode: RunMode
    base: str
    head: str
    facts: list[ChangeFact]
    sentences_checked: int
    candidates: int
    findings: list[Finding]  # after filters (suppressed_by is None)
    suppressed: list[Finding]  # for --debug and eval
    timings_ms: dict[str, int]
    models: dict[str, str]
    # example: {"tier2": "qwen3-4b-q4_k_m", "verify": "nemotron-3-ultra-550b"}

    def to_json(self) -> str:
        """Serialize to JSON."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> RunReport:
        """Deserialize from JSON."""
        return cls.model_validate_json(json_str)


# =============================================================================
# Stage function signatures (also frozen) — §3.2
# =============================================================================
#
# # extract/__init__.py
# def extract_facts(diff_text: str, repo: RepoView, cfg: Config) -> list[ChangeFact]: ...
#
# # docs/index.py
# def build_index(repo: RepoView, cfg: Config) -> DocIndex: ...
# # DocIndex.sentences: dict[str, DocSentence]
#
# # search/__init__.py
# def find_candidates(facts, index, cfg) -> list[Candidate]: ...
#
# # tier1/__init__.py
# def run_tier1(facts, index, candidates, cfg) -> tuple[list[Finding], list[Candidate]]: ...
# # (findings, leftover candidates)
#
# # llm/qwen.py
# def run_tier2(facts, index, candidates, client, cfg) -> list[Finding]: ...
#
# # llm/nemotron.py  /  llm/selfcheck.py
# def verify(findings, client, cfg) -> list[Finding]: ...
# # sets .verification
#
# # filters/__init__.py
# def apply_filters(findings, ctx: FilterContext, cfg) -> tuple[list[Finding], list[Finding]]: ...
# # (kept, suppressed)
#
# # pipeline.py
# def run(base: str, head: str, cfg: Config, *, diff_text: str | None = None) -> RunReport: ...
#
#
# class RepoView (in gitutil.py):
#     def __init__(self, root: Path, rev: str): ...
#     def read(self, path: str) -> str | None: ...       # git show rev:path
#     def list_files(self) -> list[str]: ...             # git ls-tree -r --name-only rev
