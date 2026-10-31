"""DriftCheck configuration loader."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class GeneralConfig(BaseModel):
    """General configuration."""

    fail_on: str = Field(default="high", pattern="^(critical|high|medium|low|none)$")
    report_gaps: bool = False


class DocsConfig(BaseModel):
    """Documentation discovery configuration."""

    globs: list[str] = Field(
        default_factory=lambda: [
            "docs/**/*.md",
            "docs/**/*.mdx",
            "docs/**/*.rst",
            "docs/**/*.txt",
            "README*",
        ]
    )
    exclude: list[str] = Field(
        default_factory=lambda: [
            "**/CHANGELOG*",
            "**/HISTORY*",
            "**/RELEASE*",
            "node_modules/**",
            ".venv/**",
            "site/**",
            "_build/**",
        ]
    )
    high_traffic_patterns: list[str] = Field(
        default_factory=lambda: ["quickstart", "getting-started", "install", "README"]
    )


class CodeConfig(BaseModel):
    """Code analysis configuration."""

    ignore_globs: list[str] = Field(
        default_factory=lambda: [
            "tests/**",
            "**/migrations/**",
            "**/vendor/**",
        ]
    )
    config_globs: list[str] = Field(
        default_factory=lambda: [
            ".env.example",
            "**/*.example.*",
            "**/config*.{yml,yaml,toml,json,ini}",
            "**/defaults*.*",
            "**/settings*.*",
        ]
    )


class SearchConfig(BaseModel):
    """Search and candidate configuration."""

    max_candidates_per_fact: int = 12
    bm25_top_k: int = 5
    bm25_min_score: float = 0.35
    weak_words: list[str] = Field(
        default_factory=lambda: [
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
    )


class LLMConfig(BaseModel):
    """LLM configuration."""

    mode: str = Field(default="none", pattern="^(none|local|full)$")
    tier2_base_url: str = "http://127.0.0.1:8080/v1"
    tier2_model: str = "qwen3-4b"
    tier2_min_confidence: float = 0.6
    tier2_max_sentences: int = 6
    tier2_max_calls: int = 40
    verify_base_url: str = "https://integrate.api.nvidia.com/v1"
    verify_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    verify_concurrency: int = 2
    timeout_s: int = 60
    cache: bool = True


class OutputConfig(BaseModel):
    """Output configuration."""

    max_annotations: int = 25
    max_findings_in_comment: int = 15


class HookConfig(BaseModel):
    """Git hook configuration."""

    llm: str = Field(default="none", pattern="^(none|local|full)$")
    block_on: str = Field(default="none", pattern="^(none|critical|high)$")


class Config(BaseModel):
    """Root configuration model."""

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    docs: DocsConfig = Field(default_factory=DocsConfig)
    code: CodeConfig = Field(default_factory=CodeConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    hook: HookConfig = Field(default_factory=HookConfig)

    @field_validator("general", "docs", "code", "search", "llm", "output", "hook", mode="before")
    @classmethod
    def _ensure_dict(cls, v: Any) -> Any:
        if v is None:
            return {}
        return v


def _load_toml_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from a TOML file."""
    if not config_path.exists():
        return {}
    with config_path.open("rb") as f:
        return tomllib.load(f)


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides (DRIFTCHECK_<SECTION>_<KEY>)."""
    result = dict(config)

    # Map of section names to their environment variable prefixes
    sections = {
        "general": "DRIFTCHECK_GENERAL",
        "docs": "DRIFTCHECK_DOCS",
        "code": "DRIFTCHECK_CODE",
        "search": "DRIFTCHECK_SEARCH",
        "llm": "DRIFTCHECK_LLM",
        "output": "DRIFTCHECK_OUTPUT",
        "hook": "DRIFTCHECK_HOOK",
    }

    for section, prefix in sections.items():
        section_config = result.get(section, {})
        if not isinstance(section_config, dict):
            section_config = {}
        section_config = dict(section_config)

        # Find all env vars matching this section prefix
        for key, value in os.environ.items():
            if key.startswith(prefix + "_"):
                # Extract the config key (remove prefix and underscore)
                config_key = key[len(prefix) + 1 :].lower()

                # Convert value to appropriate type
                if value.lower() in ("true", "false"):
                    section_config[config_key] = value.lower() == "true"
                elif value.isdigit():
                    section_config[config_key] = int(value)
                else:
                    try:
                        section_config[config_key] = float(value)
                    except ValueError:
                        section_config[config_key] = value

        result[section] = section_config

    return result


def load_config(repo_root: str | Path, overrides: dict[str, Any] | None = None) -> Config:
    """Load configuration with precedence: CLI flags > env vars > .driftcheck.toml > defaults.

    Args:
        repo_root: Path to the repository root (where .driftcheck.toml lives)
        overrides: CLI flag overrides (highest precedence)

    Returns:
        Config object with merged configuration
    """
    repo_path = Path(repo_root).resolve()

    # Start with defaults (empty dict will use model defaults)
    config_dict: dict[str, Any] = {}

    # Load from .driftcheck.toml
    toml_path = repo_path / ".driftcheck.toml"
    toml_config = _load_toml_config(toml_path)
    if toml_config:
        config_dict = toml_config

    # Apply environment variable overrides
    config_dict = _apply_env_overrides(config_dict)

    # Apply CLI overrides (highest precedence)
    if overrides:
        for section, values in overrides.items():
            if section in config_dict and isinstance(config_dict[section], dict):
                config_dict[section].update(values)
            else:
                config_dict[section] = values

    return Config(**config_dict)
