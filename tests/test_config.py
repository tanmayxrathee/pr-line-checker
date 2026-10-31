"""Tests for driftcheck config loader."""

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from driftcheck.config import Config, load_config


class TestConfigDefaults:
    """Test default configuration values."""

    def test_defaults(self):
        """Test that defaults match Appendix B."""
        config = Config()

        # General
        assert config.general.fail_on == "high"
        assert config.general.report_gaps is False

        # Docs
        assert config.docs.globs == [
            "docs/**/*.md",
            "docs/**/*.mdx",
            "docs/**/*.rst",
            "docs/**/*.txt",
            "README*",
        ]
        assert config.docs.exclude == [
            "**/CHANGELOG*",
            "**/HISTORY*",
            "**/RELEASE*",
            "node_modules/**",
            ".venv/**",
            "site/**",
            "_build/**",
        ]
        assert config.docs.high_traffic_patterns == [
            "quickstart",
            "getting-started",
            "install",
            "README",
        ]

        # Code
        assert config.code.ignore_globs == [
            "tests/**",
            "**/migrations/**",
            "**/vendor/**",
        ]
        assert config.code.config_globs == [
            ".env.example",
            "**/*.example.*",
            "**/config*.{yml,yaml,toml,json,ini}",
            "**/defaults*.*",
            "**/settings*.*",
        ]

        # Search
        assert config.search.max_candidates_per_fact == 12
        assert config.search.bm25_top_k == 5
        assert config.search.bm25_min_score == 0.35
        assert config.search.weak_words == [
            "timeout",
            "name",
            "path",
            "debug",
            "port",
            "host",
            "verbose",
            "config",
            "output",
            "mode",
        ]

        # LLM
        assert config.llm.mode == "none"
        assert config.llm.tier2_base_url == "http://127.0.0.1:8080/v1"
        assert config.llm.tier2_model == "qwen3-4b"
        assert config.llm.tier2_min_confidence == 0.6
        assert config.llm.tier2_max_sentences == 6
        assert config.llm.tier2_max_calls == 40
        assert config.llm.verify_base_url == "https://integrate.api.nvidia.com/v1"
        assert config.llm.verify_model == "nvidia/nemotron-3-ultra-550b-a55b"
        assert config.llm.verify_concurrency == 2
        assert config.llm.timeout_s == 60
        assert config.llm.cache is True

        # Output
        assert config.output.max_annotations == 25
        assert config.output.max_findings_in_comment == 15

        # Hook
        assert config.hook.llm == "none"
        assert config.hook.block_on == "none"


class TestConfigFromTOML:
    """Test loading configuration from TOML file."""

    def test_load_from_toml(self, tmp_path):
        """Test loading config from .driftcheck.toml."""
        toml_content = """
[general]
fail_on = "medium"
report_gaps = true

[docs]
globs = ["custom/**/*.md"]
exclude = ["**/skip/**"]
high_traffic_patterns = ["guide"]

[search]
max_candidates_per_fact = 20
bm25_top_k = 10
"""
        config_file = tmp_path / ".driftcheck.toml"
        config_file.write_text(toml_content)

        config = load_config(tmp_path)

        assert config.general.fail_on == "medium"
        assert config.general.report_gaps is True
        assert config.docs.globs == ["custom/**/*.md"]
        assert config.docs.exclude == ["**/skip/**"]
        assert config.docs.high_traffic_patterns == ["guide"]
        assert config.search.max_candidates_per_fact == 20
        assert config.search.bm25_top_k == 10

    def test_missing_toml_uses_defaults(self, tmp_path):
        """Test that missing .driftcheck.toml uses defaults."""
        config = load_config(tmp_path)

        # Should have all defaults
        assert config.general.fail_on == "high"
        assert config.llm.mode == "none"

    def test_partial_toml_merges_with_defaults(self, tmp_path):
        """Test that partial TOML merges with defaults."""
        toml_content = """
[general]
fail_on = "low"
"""
        config_file = tmp_path / ".driftcheck.toml"
        config_file.write_text(toml_content)

        config = load_config(tmp_path)

        assert config.general.fail_on == "low"
        # Other values should be defaults
        assert config.general.report_gaps is False
        assert config.llm.mode == "none"


class TestConfigEnvOverrides:
    """Test environment variable overrides."""

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        """Test that env vars override TOML config."""
        toml_content = """
[general]
fail_on = "high"
"""
        config_file = tmp_path / ".driftcheck.toml"
        config_file.write_text(toml_content)

        monkeypatch.setenv("DRIFTCHECK_GENERAL_FAIL_ON", "critical")

        config = load_config(tmp_path)

        assert config.general.fail_on == "critical"

    def test_env_overrides_nested(self, tmp_path, monkeypatch):
        """Test env vars for nested config."""
        monkeypatch.setenv("DRIFTCHECK_LLM_MODE", "local")
        monkeypatch.setenv("DRIFTCHECK_LLM_TIER2_MODEL", "custom-model")
        monkeypatch.setenv("DRIFTCHECK_LLM_TIER2_MIN_CONFIDENCE", "0.8")

        config = load_config(tmp_path)

        assert config.llm.mode == "local"
        assert config.llm.tier2_model == "custom-model"
        assert config.llm.tier2_min_confidence == 0.8

    def test_env_boolean_conversion(self, tmp_path, monkeypatch):
        """Test boolean env var conversion."""
        monkeypatch.setenv("DRIFTCHECK_GENERAL_REPORT_GAPS", "true")
        monkeypatch.setenv("DRIFTCHECK_LLM_CACHE", "false")

        config = load_config(tmp_path)

        assert config.general.report_gaps is True
        assert config.llm.cache is False

    def test_env_integer_conversion(self, tmp_path, monkeypatch):
        """Test integer env var conversion."""
        monkeypatch.setenv("DRIFTCHECK_SEARCH_MAX_CANDIDATES_PER_FACT", "25")
        monkeypatch.setenv("DRIFTCHECK_LLM_VERIFY_CONCURRENCY", "4")

        config = load_config(tmp_path)

        assert config.search.max_candidates_per_fact == 25
        assert config.llm.verify_concurrency == 4

    def test_env_float_conversion(self, tmp_path, monkeypatch):
        """Test float env var conversion."""
        monkeypatch.setenv("DRIFTCHECK_SEARCH_BM25_MIN_SCORE", "0.5")
        monkeypatch.setenv("DRIFTCHECK_LLM_TIER2_MIN_CONFIDENCE", "0.75")

        config = load_config(tmp_path)

        assert config.search.bm25_min_score == 0.5
        assert config.llm.tier2_min_confidence == 0.75

    def test_env_string_for_list_field_fails(self, tmp_path, monkeypatch):
        """Test that string env var for list field raises validation error."""
        monkeypatch.setenv("DRIFTCHECK_DOCS_GLOBS", '["a.md", "b.md"]')

        with pytest.raises(ValidationError):
            load_config(tmp_path)


class TestConfigCLIOverrides:
    """Test CLI flag overrides (highest precedence)."""

    def test_cli_overrides_env_and_toml(self, tmp_path, monkeypatch):
        """Test CLI overrides have highest precedence."""
        toml_content = """
[general]
fail_on = "high"
"""
        config_file = tmp_path / ".driftcheck.toml"
        config_file.write_text(toml_content)

        monkeypatch.setenv("DRIFTCHECK_GENERAL_FAIL_ON", "medium")

        config = load_config(tmp_path, overrides={"general": {"fail_on": "critical"}})

        assert config.general.fail_on == "critical"

    def test_cli_overrides_env(self, tmp_path, monkeypatch):
        """Test CLI overrides env vars."""
        monkeypatch.setenv("DRIFTCHECK_LLM_MODE", "local")

        config = load_config(tmp_path, overrides={"llm": {"mode": "full"}})

        assert config.llm.mode == "full"

    def test_cli_partial_override(self, tmp_path, monkeypatch):
        """Test partial CLI override merges with section."""
        monkeypatch.setenv("DRIFTCHECK_LLM_MODE", "local")
        monkeypatch.setenv("DRIFTCHECK_LLM_TIER2_MODEL", "env-model")

        config = load_config(tmp_path, overrides={"llm": {"mode": "full"}})

        assert config.llm.mode == "full"
        assert config.llm.tier2_model == "env-model"  # from env, not overridden

    def test_cli_new_section(self, tmp_path):
        """Test CLI can add new section values."""
        config = load_config(tmp_path, overrides={"general": {"fail_on": "low"}})

        assert config.general.fail_on == "low"


class TestConfigPrecedence:
    """Test full precedence order."""

    def test_full_precedence_chain(self, tmp_path, monkeypatch):
        """Test complete precedence: defaults < TOML < env < CLI."""
        toml_content = """
[general]
fail_on = "high"
report_gaps = false
"""
        config_file = tmp_path / ".driftcheck.toml"
        config_file.write_text(toml_content)

        monkeypatch.setenv("DRIFTCHECK_GENERAL_FAIL_ON", "medium")
        monkeypatch.setenv("DRIFTCHECK_GENERAL_REPORT_GAPS", "true")

        config = load_config(tmp_path, overrides={"general": {"fail_on": "critical"}})

        # CLI wins for fail_on
        assert config.general.fail_on == "critical"
        # Env wins for report_gaps (not overridden by CLI)
        assert config.general.report_gaps is True

    def test_precedence_for_different_keys(self, tmp_path, monkeypatch):
        """Test precedence works independently for different keys."""
        toml_content = """
[general]
fail_on = "high"
[llm]
mode = "none"
"""
        config_file = tmp_path / ".driftcheck.toml"
        config_file.write_text(toml_content)

        monkeypatch.setenv("DRIFTCHECK_GENERAL_FAIL_ON", "medium")
        monkeypatch.setenv("DRIFTCHECK_LLM_MODE", "local")

        config = load_config(tmp_path, overrides={"general": {"fail_on": "low"}})

        # general.fail_on: CLI (low) > env (medium) > TOML (high) > default (high)
        assert config.general.fail_on == "low"
        # llm.mode: env (local) > TOML (none) > default (none)
        assert config.llm.mode == "local"


class TestConfigValidation:
    """Test config validation."""

    def test_invalid_fail_on(self, tmp_path):
        """Test invalid fail_on value raises error."""
        toml_content = """
[general]
fail_on = "invalid"
"""
        config_file = tmp_path / ".driftcheck.toml"
        config_file.write_text(toml_content)

        with pytest.raises(ValidationError):
            load_config(tmp_path)

    def test_invalid_llm_mode(self, tmp_path):
        """Test invalid llm mode raises error."""
        toml_content = """
[llm]
mode = "invalid"
"""
        config_file = tmp_path / ".driftcheck.toml"
        config_file.write_text(toml_content)

        with pytest.raises(ValidationError):
            load_config(tmp_path)

    def test_invalid_type_in_toml(self, tmp_path):
        """Test invalid type in TOML raises error."""
        toml_content = """
[search]
max_candidates_per_fact = "not_a_number"
"""
        config_file = tmp_path / ".driftcheck.toml"
        config_file.write_text(toml_content)

        with pytest.raises(ValidationError):
            load_config(tmp_path)


class TestConfigWithTempDir:
    """Integration tests with temporary directories."""

    def test_load_config_with_real_toml_file(self):
        """Test loading config with a real TOML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            toml_content = """
[general]
fail_on = "medium"

[llm]
mode = "local"
tier2_model = "my-custom-model"
"""
            (tmp_path / ".driftcheck.toml").write_text(toml_content)

            config = load_config(tmp_path)

            assert config.general.fail_on == "medium"
            assert config.llm.mode == "local"
            assert config.llm.tier2_model == "my-custom-model"

    def test_config_is_immutable_after_load(self, tmp_path):
        """Test that config values can be accessed."""
        config = load_config(tmp_path)

        # Should be able to access all sections
        assert isinstance(config.general, object)
        assert isinstance(config.docs, object)
        assert isinstance(config.code, object)
        assert isinstance(config.search, object)
        assert isinstance(config.llm, object)
        assert isinstance(config.output, object)
        assert isinstance(config.hook, object)
