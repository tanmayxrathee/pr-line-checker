"""Config file extractor for YAML, TOML, JSON, .env.example, INI."""

from __future__ import annotations

import configparser
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from driftcheck.extract.base import FileChange, Hunk
from driftcheck.models import ChangeFact, ChangeType, CodeLocation, SymbolKind


@dataclass
class ConfigSymbol:
    """Represents a configuration key extracted from a config file."""

    key: str  # Dotted path (e.g., "server.timeout", "database.host")
    value: str | None  # String representation of the value
    line: int  # Approximate line number in source
    file_type: str  # "toml", "yaml", "json", "ini", "env"

    def signature_key(self) -> tuple:
        """Return a key for matching config keys across versions."""
        return (self.key, self.file_type)


class ConfigFilesExtractor:
    """Extract config key changes from config files."""

    name = "config_files"

    # File extensions this extractor handles
    EXTENSIONS = {
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".ini": "ini",
        ".cfg": "ini",
        ".conf": "ini",
        ".env": "env",
        ".env.example": "env",
        ".env.local": "env",
        ".env.development": "env",
        ".env.production": "env",
    }

    def applies_to(self, path: str) -> bool:
        """Check if this extractor applies to the given file path."""
        return Path(path).suffix in self.EXTENSIONS or Path(path).name in self.EXTENSIONS

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        """Extract config key changes from a file change."""
        facts: list[ChangeFact] = []

        if not old_src and not new_src:
            return facts

        file_type = self._get_file_type(fc.path)
        if not file_type:
            return facts

        # Parse old and new configs with line number tracking
        old_parsed = self._parse_config_with_lines(old_src, file_type) if old_src else {}
        new_parsed = self._parse_config_with_lines(new_src, file_type) if new_src else {}

        # Find added, removed, and changed keys
        all_keys = set(old_parsed.keys()) | set(new_parsed.keys())

        for key in all_keys:
            old_sym = old_parsed.get(key)
            new_sym = new_parsed.get(key)

            if old_sym is None and new_sym is not None:
                # Added
                fact = self._make_fact(
                    fc=fc,
                    symbol=new_sym,
                    change_type=ChangeType.ADDED,
                    old=None,
                    new=new_sym.value,
                    line_old=None,
                    line_new=new_sym.line,
                )
                if fact and self._intersects_hunks(fact, fc.hunks):
                    facts.append(fact)

            elif old_sym is not None and new_sym is None:
                # Removed
                fact = self._make_fact(
                    fc=fc,
                    symbol=old_sym,
                    change_type=ChangeType.REMOVED,
                    old=old_sym.value,
                    new=None,
                    line_old=old_sym.line,
                    line_new=None,
                )
                if fact and self._intersects_hunks(fact, fc.hunks):
                    facts.append(fact)

            elif old_sym is not None and new_sym is not None:
                # Modified - check for value change
                if old_sym.value != new_sym.value:
                    fact = self._make_fact(
                        fc=fc,
                        symbol=new_sym,
                        change_type=ChangeType.DEFAULT_CHANGED,
                        old=old_sym.value,
                        new=new_sym.value,
                        line_old=old_sym.line,
                        line_new=new_sym.line,
                    )
                    if fact and self._intersects_hunks(fact, fc.hunks):
                        facts.append(fact)

        return facts

    def _get_file_type(self, path: str) -> str | None:
        """Determine the config file type from the path."""
        path_obj = Path(path)
        # Check full name first (e.g., .env.example)
        if path_obj.name in self.EXTENSIONS:
            return self.EXTENSIONS[path_obj.name]
        # Check suffix
        return self.EXTENSIONS.get(path_obj.suffix)

    def _parse_config(self, source: str, file_type: str) -> dict[str, Any]:
        """Parse a config file based on its type (legacy method for backward compatibility)."""
        # Delegate to the new method and return just the config dict
        parsed = self._parse_config_with_lines(source, file_type)
        result: dict[str, Any] = {}
        for key, symbol in parsed.items():
            # Convert string representation back to appropriate type
            value = symbol.value
            if value is None:
                result[key] = None
            elif value.lower() in ("true", "false"):
                result[key] = value.lower() == "true"
            else:
                try:
                    # Try to parse as JSON (for arrays, numbers)
                    import json

                    result[key] = json.loads(value)
                except Exception:
                    result[key] = value
        return result

    def _flatten_config(
        self,
        config: dict[str, Any],
        file_type: str,
        prefix: str = "",
    ) -> dict[str, ConfigSymbol]:
        """Flatten a nested config dict to dotted keys.

        Legacy method for backward compatibility.
        """
        # Build a dummy line map (all lines = 1)
        line_map: dict[str, int] = {}

        def build_line_map(d: dict[str, Any], p: str = "") -> None:
            for k, v in d.items():
                dotted = f"{p}.{k}" if p else k
                line_map[dotted] = 1
                if isinstance(v, dict):
                    build_line_map(v, dotted)

        build_line_map(config)

        return self._flatten_config_with_lines(config, file_type, line_map, prefix)

    def _parse_config_with_lines(self, source: str, file_type: str) -> dict[str, ConfigSymbol]:
        """Parse a config file and return flattened keys with line numbers."""
        # First parse the raw config
        if file_type == "json":
            try:
                config = json.loads(source)
            except json.JSONDecodeError:
                return {}
        elif file_type == "toml":
            try:
                import tomllib

                config = tomllib.loads(source)
            except Exception:
                return {}
        elif file_type == "yaml":
            try:
                import yaml

                config = yaml.safe_load(source) or {}
            except Exception:
                return {}
        elif file_type == "ini":
            config = configparser.ConfigParser()
            try:
                config.read_string(source)
                result = {}
                for section in config.sections():
                    result[section] = dict(config[section])
                config = result
            except Exception:
                return {}
        elif file_type == "env":
            config = self._parse_env(source)
        else:
            return {}

        # Now we need to map keys to line numbers by parsing the source
        # We'll use a simple line-by-line approach for line estimation
        line_map = self._build_line_map(source, file_type)
        return self._flatten_config_with_lines(config, file_type, line_map)

    def _build_line_map(self, source: str, file_type: str) -> dict[str, int]:
        """Build a mapping from dotted keys to approximate line numbers."""
        line_map = {}
        lines = source.splitlines()

        if file_type == "env":
            # For .env files, each line is a key
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    line_map[key] = i
            return line_map

        # For structured formats (JSON, TOML, YAML, INI), we need a more sophisticated approach
        # We'll do a simple heuristic: track nesting level and assign line numbers
        current_prefix = ""
        in_section = None

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if file_type == "ini":
                # INI sections: [section]
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_section = stripped[1:-1]
                    continue
                if "=" in stripped and in_section:
                    key = stripped.split("=", 1)[0].strip()
                    line_map[f"{in_section}.{key}"] = i
                elif "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    line_map[key] = i
                continue

            # For JSON, TOML, YAML - simple heuristic based on indentation
            # Count leading spaces to determine nesting (unused but kept for reference)
            _ = len(line) - len(line.lstrip())
            # Remove trailing commas and colons
            clean = stripped.rstrip(",:")

            # Check for TOML-style key = value FIRST (before colon check)
            # because URLs like "postgres://..." contain colons
            if "=" in clean:
                # TOML key = value
                parts = clean.split("=", 1)
                key = parts[0].strip()
                if key:
                    dotted = f"{current_prefix}.{key}" if current_prefix else key
                    line_map[dotted] = i
            elif ":" in clean and not clean.startswith('"') and not clean.startswith("'"):
                # Key-value pair like "key: value" or '"key": value' (YAML/JSON)
                parts = clean.split(":", 1)
                key = parts[0].strip().strip('"').strip("'")
                if key:
                    dotted = f"{current_prefix}.{key}" if current_prefix else key
                    line_map[dotted] = i
            elif stripped.endswith(":") or stripped == "{":
                # Object start - track nesting
                if ":" in stripped:
                    key = stripped[:-1].strip().strip('"').strip("'")
                    if key:
                        current_prefix = f"{current_prefix}.{key}" if current_prefix else key
            elif stripped in ("}", "]"):
                # Object/array end - pop nesting
                if "." in current_prefix:
                    current_prefix = ".".join(current_prefix.split(".")[:-1])
                else:
                    current_prefix = ""

        return line_map

    def _parse_env(self, source: str) -> dict[str, Any]:
        """Parse a .env file."""
        result = {}
        for line in source.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                result[key] = value
        return result

    def _flatten_config_with_lines(
        self,
        config: dict[str, Any],
        file_type: str,
        line_map: dict[str, int],
        prefix: str = "",
    ) -> dict[str, ConfigSymbol]:
        """Flatten a nested config dict to dotted keys with line numbers."""
        flat = {}
        for key, value in config.items():
            dotted_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                # Recurse into nested dicts
                flat.update(self._flatten_config_with_lines(value, file_type, line_map, dotted_key))
            else:
                # Convert value to string representation
                if value is None:
                    value_str = None
                elif isinstance(value, bool):
                    value_str = "true" if value else "false"
                elif isinstance(value, (list, tuple)):
                    # For arrays, use JSON representation
                    value_str = json.dumps(value)
                else:
                    value_str = str(value)

                # Get line number from map, default to 1
                line = line_map.get(dotted_key, 1)

                flat[dotted_key] = ConfigSymbol(
                    key=dotted_key,
                    value=value_str,
                    line=line,
                    file_type=file_type,
                )
        return flat

    def _make_fact(
        self,
        fc: FileChange,
        symbol: ConfigSymbol,
        change_type: ChangeType,
        old: str | None,
        new: str | None,
        line_old: int | None,
        line_new: int | None,
    ) -> ChangeFact | None:
        """Create a ChangeFact from a ConfigSymbol."""
        code_snippet = self._get_code_snippet(fc.hunks, line_old, line_new)

        location = CodeLocation(
            path=fc.path,
            line_old=line_old,
            line_new=line_new,
        )

        return ChangeFact(
            id="",
            symbol=symbol.key,
            kind=SymbolKind.CONFIG_KEY,
            change_type=change_type,
            old=old,
            new=new,
            aliases=[symbol.key.split(".")[-1]],
            location=location,
            code_snippet=code_snippet,
            help_text=None,
            extractor=self.name,
            public=True,
            related=[],
        )

    def _intersects_hunks(self, fact: ChangeFact, hunks: list[Hunk]) -> bool:
        """Check if a fact's line intersects with any hunk."""
        line = fact.location.line_new or fact.location.line_old
        if line is None:
            return False

        for hunk in hunks:
            if hunk.new_start <= line < hunk.new_start + hunk.new_len:
                return True
            if hunk.old_start <= line < hunk.old_start + hunk.old_len:
                return True
        return False

    def _get_code_snippet(
        self, hunks: list[Hunk], line_old: int | None, line_new: int | None
    ) -> str:
        """Extract relevant code snippet from hunks."""
        target_line = line_new or line_old
        if target_line is None:
            return ""

        lines: list[str] = []
        for hunk in hunks:
            for tag, old_no, new_no, text in hunk.lines:
                if new_no and abs(new_no - target_line) <= 3:
                    prefix = "+" if tag == "+" else ("-" if tag == "-" else " ")
                    lines.append(f"{prefix}{text.rstrip()}")
                elif old_no and abs(old_no - target_line) <= 3:
                    prefix = "+" if tag == "+" else ("-" if tag == "-" else " ")
                    lines.append(f"{prefix}{text.rstrip()}")

        return "\n".join(lines[:20])
