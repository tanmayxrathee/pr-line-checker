"""Tests for ConfigFilesExtractor."""

from __future__ import annotations

from driftcheck.extract.base import FileChange, Hunk
from driftcheck.extract.config_files import ConfigFilesExtractor, ConfigSymbol
from driftcheck.models import ChangeType, SymbolKind


class TestConfigFilesExtractor:
    """Test the ConfigFilesExtractor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = ConfigFilesExtractor()

    # ===== Basic applicability tests =====

    def test_applies_to_toml(self):
        """Test that extractor applies to .toml files."""
        assert self.extractor.applies_to("config.toml")
        assert self.extractor.applies_to("pyproject.toml")

    def test_applies_to_yaml(self):
        """Test that extractor applies to .yaml and .yml files."""
        assert self.extractor.applies_to("config.yaml")
        assert self.extractor.applies_to("config.yml")

    def test_applies_to_json(self):
        """Test that extractor applies to .json files."""
        assert self.extractor.applies_to("config.json")

    def test_applies_to_ini(self):
        """Test that extractor applies to .ini, .cfg, .conf files."""
        assert self.extractor.applies_to("config.ini")
        assert self.extractor.applies_to("config.cfg")
        assert self.extractor.applies_to("config.conf")

    def test_applies_to_env(self):
        """Test that extractor applies to .env files."""
        assert self.extractor.applies_to(".env")
        assert self.extractor.applies_to(".env.example")
        assert self.extractor.applies_to(".env.local")
        assert self.extractor.applies_to(".env.development")
        assert self.extractor.applies_to(".env.production")

    def test_does_not_apply_to_unknown(self):
        """Test that extractor does not apply to unknown extensions."""
        assert not self.extractor.applies_to("config.txt")
        assert not self.extractor.applies_to("config.xml")

    # ===== ConfigSymbol tests =====

    def test_config_symbol_signature_key(self):
        """Test ConfigSymbol signature_key for matching."""
        sym = ConfigSymbol(
            key="server.timeout",
            value="30",
            line=1,
            file_type="toml",
        )
        key = sym.signature_key()
        assert key == ("server.timeout", "toml")

    # ===== TOML tests =====

    def test_extract_added_toml_key(self):
        """Test detecting an added TOML key."""
        old_src = "server.timeout = 30\n"
        new_src = 'server.timeout = 30\nserver.host = "localhost"\n'

        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "server.timeout = 30\n"),
                        ("+", None, 2, 'server.host = "localhost"\n'),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].symbol == "server.host"
        assert added[0].new == "localhost"
        assert added[0].kind == SymbolKind.CONFIG_KEY

    def test_extract_removed_toml_key(self):
        """Test detecting a removed TOML key."""
        old_src = 'server.timeout = 30\nserver.host = "localhost"\n'
        new_src = "server.timeout = 30\n"

        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=1,
                    lines=[
                        (" ", 1, 1, "server.timeout = 30\n"),
                        ("-", 2, None, 'server.host = "localhost"\n'),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        removed = [f for f in facts if f.change_type == ChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].symbol == "server.host"
        assert removed[0].old == "localhost"

    def test_extract_changed_toml_value(self):
        """Test detecting a changed TOML value."""
        old_src = "server.timeout = 30\n"
        new_src = "server.timeout = 60\n"

        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        ("-", 1, None, "server.timeout = 30\n"),
                        ("+", None, 1, "server.timeout = 60\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "server.timeout"
        assert changed[0].old == "30"
        assert changed[0].new == "60"

    def test_extract_nested_toml(self):
        """Test extracting nested TOML keys."""
        old_src = """
[server]
timeout = 30
host = "localhost"

[database]
url = "postgres://localhost/db"
"""
        new_src = """
[server]
timeout = 60
host = "localhost"

[database]
url = "postgres://localhost/db"
pool_size = 10
"""

        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=7,
                    new_start=1,
                    new_len=8,
                    lines=[
                        (" ", 1, 1, "\n"),
                        (" ", 2, 2, "[server]\n"),
                        ("-", 3, None, "timeout = 30\n"),
                        ("+", None, 3, "timeout = 60\n"),
                        (" ", 4, 4, 'host = "localhost"\n'),
                        (" ", 5, 5, "\n"),
                        (" ", 6, 6, "[database]\n"),
                        (" ", 7, 7, 'url = "postgres://localhost/db"\n'),
                        ("+", None, 8, "pool_size = 10\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]

        assert len(added) == 1
        assert added[0].symbol == "database.pool_size"
        assert added[0].new == "10"

        assert len(changed) == 1
        assert changed[0].symbol == "server.timeout"
        assert changed[0].old == "30"
        assert changed[0].new == "60"

    def test_extract_toml_arrays(self):
        """Test extracting TOML arrays."""
        old_src = 'allowed_hosts = ["localhost", "127.0.0.1"]\n'
        new_src = 'allowed_hosts = ["localhost", "127.0.0.1", "example.com"]\n'

        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        (
                            "-",
                            1,
                            None,
                            'allowed_hosts = ["localhost", "127.0.0.1"]\n',
                        ),
                        (
                            "+",
                            None,
                            1,
                            'allowed_hosts = ["localhost", "127.0.0.1", "example.com"]\n',
                        ),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "allowed_hosts"
        assert "example.com" in changed[0].new

    def test_extract_toml_boolean(self):
        """Test extracting TOML boolean values."""
        old_src = "debug = false\n"
        new_src = "debug = true\n"

        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        ("-", 1, None, "debug = false\n"),
                        ("+", None, 1, "debug = true\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "debug"
        assert changed[0].old == "false"
        assert changed[0].new == "true"

    # ===== JSON tests =====

    def test_extract_added_json_key(self):
        """Test detecting an added JSON key."""
        old_src = '{"server": {"timeout": 30}}'
        new_src = '{"server": {"timeout": 30}, "debug": true}'

        fc = FileChange(
            old_path="config.json",
            new_path="config.json",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        ("-", 1, None, old_src + "\n"),
                        ("+", None, 1, new_src + "\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].symbol == "debug"
        assert added[0].new == "true"

    def test_extract_changed_json_value(self):
        """Test detecting a changed JSON value."""
        old_src = '{"server": {"timeout": 30}}'
        new_src = '{"server": {"timeout": 60}}'

        fc = FileChange(
            old_path="config.json",
            new_path="config.json",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        ("-", 1, None, old_src + "\n"),
                        ("+", None, 1, new_src + "\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "server.timeout"
        assert changed[0].old == "30"
        assert changed[0].new == "60"

    def test_extract_json_arrays(self):
        """Test extracting JSON arrays."""
        old_src = '{"tags": ["a", "b"]}'
        new_src = '{"tags": ["a", "b", "c"]}'

        fc = FileChange(
            old_path="config.json",
            new_path="config.json",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        ("-", 1, None, old_src + "\n"),
                        ("+", None, 1, new_src + "\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "tags"
        assert "c" in changed[0].new

    # ===== YAML tests =====

    def test_extract_added_yaml_key(self):
        """Test detecting an added YAML key."""
        old_src = "server:\n  timeout: 30\n"
        new_src = "server:\n  timeout: 30\n  host: localhost\n"

        fc = FileChange(
            old_path="config.yaml",
            new_path="config.yaml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=3,
                    lines=[
                        (" ", 1, 1, "server:\n"),
                        (" ", 2, 2, "  timeout: 30\n"),
                        ("+", None, 3, "  host: localhost\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].symbol == "server.host"
        assert added[0].new == "localhost"

    def test_extract_yaml_list(self):
        """Test extracting YAML lists."""
        old_src = "tags:\n  - a\n  - b\n"
        new_src = "tags:\n  - a\n  - b\n  - c\n"

        fc = FileChange(
            old_path="config.yaml",
            new_path="config.yaml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=3,
                    new_start=1,
                    new_len=4,
                    lines=[
                        (" ", 1, 1, "tags:\n"),
                        (" ", 2, 2, "  - a\n"),
                        (" ", 3, 3, "  - b\n"),
                        ("+", None, 4, "  - c\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "tags"
        assert "c" in changed[0].new

    # ===== INI tests =====

    def test_extract_added_ini_key(self):
        """Test detecting an added INI key."""
        old_src = "[server]\ntimeout = 30\n"
        new_src = "[server]\ntimeout = 30\nhost = localhost\n"

        fc = FileChange(
            old_path="config.ini",
            new_path="config.ini",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=3,
                    lines=[
                        (" ", 1, 1, "[server]\n"),
                        (" ", 2, 2, "timeout = 30\n"),
                        ("+", None, 3, "host = localhost\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].symbol == "server.host"
        assert added[0].new == "localhost"

    def test_extract_changed_ini_value(self):
        """Test detecting a changed INI value."""
        old_src = "[server]\ntimeout = 30\n"
        new_src = "[server]\ntimeout = 60\n"

        fc = FileChange(
            old_path="config.ini",
            new_path="config.ini",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "[server]\n"),
                        ("-", 2, None, "timeout = 30\n"),
                        ("+", None, 2, "timeout = 60\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "server.timeout"
        assert changed[0].old == "30"
        assert changed[0].new == "60"

    # ===== .env tests =====

    def test_extract_added_env_var(self):
        """Test detecting an added .env variable."""
        old_src = "TIMEOUT=30\n"
        new_src = "TIMEOUT=30\nHOST=localhost\n"

        fc = FileChange(
            old_path=".env",
            new_path=".env",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "TIMEOUT=30\n"),
                        ("+", None, 2, "HOST=localhost\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].symbol == "HOST"
        assert added[0].new == "localhost"

    def test_extract_changed_env_var(self):
        """Test detecting a changed .env variable."""
        old_src = "TIMEOUT=30\n"
        new_src = "TIMEOUT=60\n"

        fc = FileChange(
            old_path=".env",
            new_path=".env",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        ("-", 1, None, "TIMEOUT=30\n"),
                        ("+", None, 1, "TIMEOUT=60\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "TIMEOUT"
        assert changed[0].old == "30"
        assert changed[0].new == "60"

    def test_extract_env_with_quotes(self):
        """Test extracting .env values with quotes."""
        old_src = 'API_KEY="secret123"\n'
        new_src = 'API_KEY="newsecret456"\n'

        fc = FileChange(
            old_path=".env",
            new_path=".env",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        ("-", 1, None, 'API_KEY="secret123"\n'),
                        ("+", None, 1, 'API_KEY="newsecret456"\n'),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "API_KEY"
        assert changed[0].old == "secret123"
        assert changed[0].new == "newsecret456"

    def test_extract_env_ignores_comments(self):
        """Test that .env comments are ignored."""
        old_src = "# This is a comment\nTIMEOUT=30\n"
        new_src = "# This is a comment\nTIMEOUT=60\n"

        fc = FileChange(
            old_path=".env",
            new_path=".env",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "# This is a comment\n"),
                        ("-", 2, None, "TIMEOUT=30\n"),
                        ("+", None, 2, "TIMEOUT=60\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "TIMEOUT"

    # ===== Hunk intersection tests =====

    def test_ignores_changes_outside_hunks(self):
        """Test that changes outside diff hunks are ignored."""
        old_src = """server.timeout = 30
server.host = "localhost"
database.url = "postgres://localhost/db"
"""
        new_src = """server.timeout = 30
server.host = "localhost"
database.url = "postgres://remote/db"
"""

        # Hunk only covers the last line
        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=3,
                    old_len=1,
                    new_start=3,
                    new_len=1,
                    lines=[
                        ("-", 3, None, 'database.url = "postgres://localhost/db"\n'),
                        ("+", None, 3, 'database.url = "postgres://remote/db"\n'),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        # Should only detect database.url change
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "database.url"

    # ===== Edge cases =====

    def test_extract_empty_file(self):
        """Test extracting from empty file."""
        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="added",
            hunks=[],
        )

        facts = self.extractor.extract(fc, None, "key = value\n")
        assert len(facts) == 0  # No hunks, so no facts

    def test_extract_removed_file(self):
        """Test extracting from removed file."""
        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="removed",
            hunks=[],
        )

        facts = self.extractor.extract(fc, "key = value\n", None)
        assert len(facts) == 0  # No hunks, so no facts

    def test_extract_malformed_config(self):
        """Test handling malformed config files."""
        old_src = "not valid toml [\n"
        new_src = 'key = "value"\n'

        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        ("-", 1, None, "not valid toml [\n"),
                        ("+", None, 1, 'key = "value"\n'),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        # Should handle gracefully - malformed old config parses as empty
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].symbol == "key"

    def test_extract_fact_structure(self):
        """Test that extracted facts have correct structure."""
        old_src = "timeout = 30\n"
        new_src = "timeout = 60\n"

        fc = FileChange(
            old_path="config.toml",
            new_path="config.toml",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=1,
                    lines=[
                        ("-", 1, None, "timeout = 30\n"),
                        ("+", None, 1, "timeout = 60\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]

        assert len(changed) == 1
        fact = changed[0]
        # ID is assigned later in pipeline (_assign_ids), so we check other fields
        assert fact.symbol == "timeout"
        assert fact.kind == SymbolKind.CONFIG_KEY
        assert fact.change_type == ChangeType.DEFAULT_CHANGED
        assert fact.old == "30"
        assert fact.new == "60"
        assert fact.location.path == "config.toml"
        assert fact.extractor == "config_files"
        assert fact.public is True
        assert isinstance(fact.aliases, list)
        assert isinstance(fact.related, list)


class TestConfigFilesExtractorMultipleFormats:
    """Test extractor with various config file formats in one test."""

    def setup_method(self):
        self.extractor = ConfigFilesExtractor()

    def test_all_formats_consistency(self):
        """Test that all formats produce consistent key names."""
        # TOML
        toml_config = extractor._parse_config("server.timeout = 30\n", "toml")
        toml_flat = extractor._flatten_config(toml_config, "toml")

        # JSON
        json_config = extractor._parse_config('{"server": {"timeout": 30}}', "json")
        json_flat = extractor._flatten_config(json_config, "json")

        # YAML
        yaml_config = extractor._parse_config("server:\n  timeout: 30\n", "yaml")
        yaml_flat = extractor._flatten_config(yaml_config, "yaml")

        # INI
        ini_config = extractor._parse_config("[server]\ntimeout = 30\n", "ini")
        ini_flat = extractor._flatten_config(ini_config, "ini")

        # All should have the same dotted key
        assert "server.timeout" in toml_flat
        assert "server.timeout" in json_flat
        assert "server.timeout" in yaml_flat
        assert "server.timeout" in ini_flat


# Need to import extractor at module level for the last test
extractor = ConfigFilesExtractor()
