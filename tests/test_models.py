"""Tests for driftcheck models (contracts)."""

import json

from driftcheck.models import (
    BlockType,
    Candidate,
    ChangeFact,
    ChangeType,
    CodeLocation,
    DocSentence,
    Finding,
    MatchType,
    RunMode,
    RunReport,
    Severity,
    SymbolKind,
    Tier,
    Verification,
)


class TestEnums:
    """Test enum values serialize as strings."""

    def test_symbol_kind_values(self):
        assert SymbolKind.CLI_FLAG.value == "cli_flag"
        assert SymbolKind.ENV_VAR.value == "env_var"
        assert SymbolKind.CONFIG_KEY.value == "config_key"
        assert SymbolKind.FUNCTION.value == "function"
        assert SymbolKind.CLASS.value == "class"
        assert SymbolKind.PARAMETER.value == "parameter"
        assert SymbolKind.CONSTANT.value == "constant"
        assert SymbolKind.FIELD.value == "field"
        assert SymbolKind.CHOICE.value == "choice"
        assert SymbolKind.ENDPOINT.value == "endpoint"

    def test_change_type_values(self):
        assert ChangeType.ADDED.value == "added"
        assert ChangeType.REMOVED.value == "removed"
        assert ChangeType.RENAMED.value == "renamed"
        assert ChangeType.DEFAULT_CHANGED.value == "default_changed"
        assert ChangeType.TYPE_CHANGED.value == "type_changed"
        assert ChangeType.CHOICES_CHANGED.value == "choices_changed"
        assert ChangeType.SIGNATURE_CHANGED.value == "signature_changed"
        assert ChangeType.BEHAVIOR_CHANGED.value == "behavior_changed"

    def test_block_type_values(self):
        assert BlockType.PROSE.value == "prose"
        assert BlockType.LIST_ITEM.value == "list_item"
        assert BlockType.TABLE_ROW.value == "table_row"
        assert BlockType.HEADING.value == "heading"
        assert BlockType.CODE.value == "code"
        assert BlockType.ADMONITION.value == "admonition"

    def test_match_type_values(self):
        assert MatchType.EXACT_OLD.value == "exact_old"
        assert MatchType.EXACT_SYMBOL.value == "exact_symbol"
        assert MatchType.BM25.value == "bm25"
        assert MatchType.LINK.value == "link"

    def test_tier_values(self):
        assert Tier.HARD.value == "tier1"
        assert Tier.SOFT.value == "tier2"

    def test_severity_values(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.INFO.value == "info"

    def test_run_mode_values(self):
        assert RunMode.NONE.value == "none"
        assert RunMode.LOCAL.value == "local"
        assert RunMode.FULL.value == "full"


class TestCodeLocation:
    """Tests for CodeLocation model."""

    def test_basic(self):
        loc = CodeLocation(path="src/cli.py", line_old=10, line_new=12, commit="abc123")
        assert loc.path == "src/cli.py"
        assert loc.line_old == 10
        assert loc.line_new == 12
        assert loc.commit == "abc123"

    def test_optional_fields(self):
        loc = CodeLocation(path="src/cli.py")
        assert loc.line_old is None
        assert loc.line_new is None
        assert loc.commit is None


class TestChangeFact:
    """Tests for ChangeFact model."""

    def test_basic(self):
        fact = ChangeFact(
            id="F1",
            symbol="--timeout",
            kind=SymbolKind.CLI_FLAG,
            change_type=ChangeType.RENAMED,
            old="--timeout",
            new="--request-timeout",
            location=CodeLocation(path="src/cli.py", line_new=42),
            code_snippet=(
                "- parser.add_argument('--timeout')\n+ parser.add_argument('--request-timeout')"
            ),
            extractor="py_cli",
        )
        assert fact.id == "F1"
        assert fact.symbol == "--timeout"
        assert fact.kind == SymbolKind.CLI_FLAG
        assert fact.change_type == ChangeType.RENAMED
        assert fact.old == "--timeout"
        assert fact.new == "--request-timeout"
        assert fact.aliases == []
        assert fact.public is True
        assert fact.related == []

    def test_with_aliases_and_related(self):
        fact = ChangeFact(
            id="F2",
            symbol="--request-timeout",
            kind=SymbolKind.CLI_FLAG,
            change_type=ChangeType.DEFAULT_CHANGED,
            old="30",
            new="60",
            aliases=["--request_timeout", "request_timeout"],
            location=CodeLocation(path="src/cli.py", line_new=42),
            code_snippet="...",
            extractor="py_cli",
            related=["F1"],
        )
        assert fact.aliases == ["--request_timeout", "request_timeout"]
        assert fact.related == ["F1"]


class TestDocSentence:
    """Tests for DocSentence model."""

    def test_basic(self):
        sent = DocSentence(
            id="S1",
            path="docs/usage.md",
            line_start=10,
            line_end=10,
            text="Use `--timeout` to set the timeout.",
            plain="Use --timeout to set the timeout.",
            block=BlockType.PROSE,
            heading_path=["Usage"],
            code_spans=["`--timeout`"],
        )
        assert sent.id == "S1"
        assert sent.path == "docs/usage.md"
        assert sent.line_start == 10
        assert sent.line_end == 10
        assert sent.block == BlockType.PROSE
        assert sent.heading_path == ["Usage"]
        assert sent.code_spans == ["`--timeout`"]
        assert sent.ignored is False


class TestCandidate:
    """Tests for Candidate model."""

    def test_basic(self):
        cand = Candidate(
            fact_id="F1",
            sentence_id="S1",
            match=MatchType.EXACT_SYMBOL,
            score=1.0,
            matched_token="--timeout",
        )
        assert cand.fact_id == "F1"
        assert cand.sentence_id == "S1"
        assert cand.match == MatchType.EXACT_SYMBOL
        assert cand.score == 1.0
        assert cand.matched_token == "--timeout"


class TestVerification:
    """Tests for Verification model."""

    def test_basic(self):
        ver = Verification(
            by="nemotron-3-ultra",
            decision="confirm",
            confidence=0.95,
            reason="Clear match",
        )
        assert ver.by == "nemotron-3-ultra"
        assert ver.decision == "confirm"
        assert ver.confidence == 0.95
        assert ver.reason == "Clear match"

    def test_default_reason(self):
        ver = Verification(by="qwen-selfcheck", decision="reject", confidence=0.3)
        assert ver.reason == ""


class TestFinding:
    """Tests for Finding model."""

    def test_basic(self):
        fact = ChangeFact(
            id="F1",
            symbol="--timeout",
            kind=SymbolKind.CLI_FLAG,
            change_type=ChangeType.REMOVED,
            old="--timeout",
            location=CodeLocation(path="src/cli.py", line_old=42),
            code_snippet="- parser.add_argument('--timeout')",
            extractor="py_cli",
        )
        sent = DocSentence(
            id="S1",
            path="docs/usage.md",
            line_start=10,
            line_end=10,
            text="Use `--timeout` to set the timeout.",
            plain="Use --timeout to set the timeout.",
            block=BlockType.PROSE,
        )
        finding = Finding(
            id="D1",
            fingerprint="abc123",
            tier=Tier.HARD,
            rule="R1_removed_flag",
            severity=Severity.CRITICAL,
            confidence=1.0,
            fact=fact,
            sentence=sent,
            doc_quote="`--timeout`",
            code_quote="parser.add_argument('--timeout')",
            message=(
                "`--timeout` was removed in cli.py:42, but docs/usage.md:10 still uses `--timeout`."
            ),
        )
        assert finding.id == "D1"
        assert finding.fingerprint == "abc123"
        assert finding.tier == Tier.HARD
        assert finding.rule == "R1_removed_flag"
        assert finding.severity == Severity.CRITICAL
        assert finding.confidence == 1.0
        assert finding.suggested_text is None
        assert finding.verification is None
        assert finding.suppressed_by is None

    def test_compute_fingerprint(self):
        """Test fingerprint computation is stable."""
        rule = "R1_removed_flag"
        kind = SymbolKind.CLI_FLAG
        symbol = "--timeout"
        old = "--timeout"
        sentence_plain = "Use --timeout to set the timeout."

        fp1 = Finding.compute_fingerprint(rule, kind, symbol, old, sentence_plain)
        fp2 = Finding.compute_fingerprint(rule, kind, symbol, old, sentence_plain)
        assert fp1 == fp2
        assert len(fp1) == 16  # SHA1 truncated to 16 chars

    def test_fingerprint_changes_with_sentence(self):
        """Test fingerprint changes when sentence text changes."""
        rule = "R1_removed_flag"
        kind = SymbolKind.CLI_FLAG
        symbol = "--timeout"
        old = "--timeout"

        sent1 = "Use --timeout to set the timeout."
        sent2 = "Use --request-timeout to set the timeout."
        fp1 = Finding.compute_fingerprint(rule, kind, symbol, old, sent1)
        fp2 = Finding.compute_fingerprint(rule, kind, symbol, old, sent2)
        assert fp1 != fp2

    def test_fingerprint_changes_with_rule(self):
        """Test fingerprint changes when rule changes."""
        kind = SymbolKind.CLI_FLAG
        symbol = "--timeout"
        old = "--timeout"
        sentence_plain = "Use --timeout to set the timeout."

        fp1 = Finding.compute_fingerprint("R1_removed_flag", kind, symbol, old, sentence_plain)
        fp2 = Finding.compute_fingerprint("R2_renamed_flag", kind, symbol, old, sentence_plain)
        assert fp1 != fp2


class TestRunReport:
    """Tests for RunReport model."""

    def test_basic(self):
        report = RunReport(
            tool_version="0.1.0",
            mode=RunMode.NONE,
            base="HEAD~1",
            head="HEAD",
            facts=[],
            sentences_checked=100,
            candidates=5,
            findings=[],
            suppressed=[],
            timings_ms={"extract": 50, "index": 30, "search": 20, "tier1": 10, "total": 110},
            models={"tier2": "none", "verify": "none"},
        )
        assert report.tool_version == "0.1.0"
        assert report.mode == RunMode.NONE
        assert report.sentences_checked == 100
        assert report.candidates == 5

    def test_json_roundtrip(self):
        """Test JSON serialization round-trip."""
        fact = ChangeFact(
            id="F1",
            symbol="--timeout",
            kind=SymbolKind.CLI_FLAG,
            change_type=ChangeType.REMOVED,
            old="--timeout",
            location=CodeLocation(path="src/cli.py", line_old=42),
            code_snippet="- parser.add_argument('--timeout')",
            extractor="py_cli",
        )
        sent = DocSentence(
            id="S1",
            path="docs/usage.md",
            line_start=10,
            line_end=10,
            text="Use `--timeout` to set the timeout.",
            plain="Use --timeout to set the timeout.",
            block=BlockType.PROSE,
        )
        finding = Finding(
            id="D1",
            fingerprint="abc123def4567890",
            tier=Tier.HARD,
            rule="R1_removed_flag",
            severity=Severity.CRITICAL,
            confidence=1.0,
            fact=fact,
            sentence=sent,
            doc_quote="`--timeout`",
            code_quote="parser.add_argument('--timeout')",
            message="Test finding",
        )
        report = RunReport(
            tool_version="0.1.0",
            mode=RunMode.NONE,
            base="HEAD~1",
            head="HEAD",
            facts=[fact],
            sentences_checked=100,
            candidates=5,
            findings=[finding],
            suppressed=[],
            timings_ms={"total": 110},
            models={"tier2": "none", "verify": "none"},
        )

        # Serialize to JSON
        json_str = report.to_json()
        assert isinstance(json_str, str)

        # Deserialize from JSON
        report2 = RunReport.from_json(json_str)
        assert report2.tool_version == report.tool_version
        assert report2.mode == report.mode
        assert report2.base == report.base
        assert report2.head == report.head
        assert len(report2.facts) == 1
        assert report2.facts[0].id == "F1"
        assert len(report2.findings) == 1
        assert report2.findings[0].id == "D1"
        assert report2.findings[0].fingerprint == "abc123def4567890"

    def test_json_contains_expected_fields(self):
        """Test JSON output contains all expected fields."""
        report = RunReport(
            tool_version="0.1.0",
            mode=RunMode.NONE,
            base="HEAD~1",
            head="HEAD",
            facts=[],
            sentences_checked=0,
            candidates=0,
            findings=[],
            suppressed=[],
            timings_ms={},
            models={},
        )
        json_str = report.to_json()
        data = json.loads(json_str)

        expected_fields = {
            "tool_version",
            "mode",
            "base",
            "head",
            "facts",
            "sentences_checked",
            "candidates",
            "findings",
            "suppressed",
            "timings_ms",
            "models",
        }
        assert set(data.keys()) == expected_fields


class TestEnumSerialization:
    """Test that enums serialize as strings in JSON."""

    def test_symbol_kind_json(self):
        fact = ChangeFact(
            id="F1",
            symbol="--timeout",
            kind=SymbolKind.CLI_FLAG,
            change_type=ChangeType.REMOVED,
            old="--timeout",
            location=CodeLocation(path="src/cli.py"),
            code_snippet="...",
            extractor="py_cli",
        )
        json_str = fact.model_dump_json()
        data = json.loads(json_str)
        assert data["kind"] == "cli_flag"  # string, not enum

    def test_severity_json(self):
        fact = ChangeFact(
            id="F1",
            symbol="--timeout",
            kind=SymbolKind.CLI_FLAG,
            change_type=ChangeType.REMOVED,
            old="--timeout",
            location=CodeLocation(path="src/cli.py"),
            code_snippet="...",
            extractor="py_cli",
        )
        sent = DocSentence(
            id="S1",
            path="docs/usage.md",
            line_start=10,
            line_end=10,
            text="...",
            plain="...",
            block=BlockType.PROSE,
        )
        finding = Finding(
            id="D1",
            fingerprint="abc123",
            tier=Tier.HARD,
            rule="R1",
            severity=Severity.CRITICAL,
            confidence=1.0,
            fact=fact,
            sentence=sent,
            doc_quote="...",
            code_quote="...",
            message="...",
        )
        json_str = finding.model_dump_json()
        data = json.loads(json_str)
        assert data["severity"] == "critical"  # string, not enum
        assert data["tier"] == "tier1"  # string, not enum
