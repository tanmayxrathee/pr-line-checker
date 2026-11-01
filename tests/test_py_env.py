"""Tests for EnvExtractor."""

from __future__ import annotations

from driftcheck.extract.base import FileChange, Hunk
from driftcheck.extract.py_env import EnvExtractor, EnvSymbol
from driftcheck.models import ChangeType, SymbolKind


class TestEnvExtractor:
    """Test the EnvExtractor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = EnvExtractor()

    # ===== Basic applicability tests =====

    def test_applies_to_py_files(self):
        """Test that extractor applies to .py files."""
        assert self.extractor.applies_to("config.py")
        assert self.extractor.applies_to("src/settings.py")

    def test_does_not_apply_to_non_py(self):
        """Test that extractor does not apply to non-Python files."""
        assert not self.extractor.applies_to("config.toml")
        assert not self.extractor.applies_to("config.yaml")
        assert not self.extractor.applies_to(".env")
        assert not self.extractor.applies_to("config.json")

    # ===== EnvSymbol tests =====

    def test_env_symbol_signature_key(self):
        """Test EnvSymbol signature_key for matching."""
        sym = EnvSymbol(
            name="DATABASE_URL",
            kind="getenv",
            line=1,
            default_value=None,
            call_args=(),
        )
        key = sym.signature_key()
        assert key == ("DATABASE_URL", "getenv")

    # ===== os.getenv tests =====

    def test_extract_os_getenv_basic(self):
        """Test detecting basic os.getenv call."""
        old_src = "import os\nurl = os.getenv('DATABASE_URL')\n"
        new_src = old_src

        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "import os\n"),
                        (" ", 2, 2, "url = os.getenv('DATABASE_URL')\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        # No changes expected
        assert len(facts) == 0

    def test_extract_added_getenv(self):
        """Test detecting an added os.getenv call."""
        old_src = "import os\n"
        new_src = "import os\nurl = os.getenv('DATABASE_URL')\n"

        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=1,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "import os\n"),
                        ("+", None, 2, "url = os.getenv('DATABASE_URL')\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].symbol == "DATABASE_URL"
        assert added[0].kind == SymbolKind.ENV_VAR

    def test_extract_removed_getenv(self):
        """Test detecting a removed os.getenv call."""
        old_src = "import os\nurl = os.getenv('DATABASE_URL')\n"
        new_src = "import os\n"

        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=1,
                    lines=[
                        (" ", 1, 1, "import os\n"),
                        ("-", 2, None, "url = os.getenv('DATABASE_URL')\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        removed = [f for f in facts if f.change_type == ChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].symbol == "DATABASE_URL"

    def test_extract_getenv_with_default(self):
        """Test detecting os.getenv with default value."""
        old_src = "import os\nurl = os.getenv('DATABASE_URL')\n"
        new_src = "import os\nurl = os.getenv('DATABASE_URL', 'postgres://localhost/db')\n"

        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "import os\n"),
                        ("-", 2, None, "url = os.getenv('DATABASE_URL')\n"),
                        ("+", None, 2, "url = os.getenv('DATABASE_URL', 'postgres://localhost/db')\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "DATABASE_URL"
        assert "default" in changed[0].new
        assert "postgres" in changed[0].new

    def test_extract_from_os_import_getenv(self):
        """Test detecting getenv when imported directly."""
        src = "from os import getenv\nurl = getenv('DATABASE_URL')\n"
        symbols = self.extractor._extract_symbols(src)
        assert len(symbols) == 1
        sym = list(symbols.values())[0]
        assert sym.name == "DATABASE_URL"
        assert sym.kind == "getenv"

    # ===== os.environ tests =====

    def test_extract_environ_subscript(self):
        """Test detecting environ['VAR'] access."""
        old_src = "from os import environ\nhost = environ['HOST']\n"
        new_src = "from os import environ\nhost = environ['HOST']\n"

        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "from os import environ\n"),
                        (" ", 2, 2, "host = environ['HOST']\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        assert len(facts) == 0

    def test_extract_os_environ_subscript(self):
        """Test detecting os.environ['VAR'] access."""
        src = "import os\nhost = os.environ['HOST']\n"
        symbols = self.extractor._extract_symbols(src)
        assert len(symbols) == 1
        sym = list(symbols.values())[0]
        assert sym.name == "HOST"
        assert sym.kind == "environ"

    def test_extract_environ_get(self):
        """Test detecting os.environ.get('VAR', default)."""
        old_src = "import os\nport = os.environ.get('PORT')\n"
        new_src = "import os\nport = os.environ.get('PORT', '8080')\n"

        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "import os\n"),
                        ("-", 2, None, "port = os.environ.get('PORT')\n"),
                        ("+", None, 2, "port = os.environ.get('PORT', '8080')\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "PORT"
        assert "8080" in changed[0].new

    # ===== Pydantic tests =====

    def test_extract_pydantic_field(self):
        """Test detecting pydantic Field(env='VAR')."""
        src = "from pydantic import Field\nurl = Field(env='DATABASE_URL', default='postgres://localhost/db')\n"
        symbols = self.extractor._extract_symbols(src)
        assert len(symbols) == 1
        sym = list(symbols.values())[0]
        assert sym.name == "DATABASE_URL"
        assert sym.kind == "pydantic_field"
        assert sym.default_value == "'postgres://localhost/db'"

    def test_extract_pydantic_settings_class(self):
        """Test detecting env vars in pydantic Settings class."""
        src = """
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    database_url: str = Field(env='DATABASE_URL')
    api_key: str = Field(env='API_KEY', default='secret')
"""
        symbols = self.extractor._extract_symbols(src)
        assert len(symbols) == 2
        names = {s.name for s in symbols.values()}
        assert "DATABASE_URL" in names
        assert "API_KEY" in names

        api_key_sym = [s for s in symbols.values() if s.name == "API_KEY"][0]
        assert api_key_sym.default_value == "'secret'"

    def test_extract_pydantic_default_changed(self):
        """Test detecting default value change in pydantic Field."""
        old_src = """
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    database_url: str = Field(env='DATABASE_URL')
"""
        new_src = """
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    database_url: str = Field(env='DATABASE_URL', default='postgres://localhost/db')
"""

        fc = FileChange(
            old_path="settings.py",
            new_path="settings.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=5,
                    new_start=1,
                    new_len=5,
                    lines=[
                        (" ", 1, 1, "from pydantic import BaseSettings, Field\n"),
                        (" ", 2, 2, "\n"),
                        (" ", 3, 3, "class Settings(BaseSettings):\n"),
                        ("-", 4, None, "    database_url: str = Field(env='DATABASE_URL')\n"),
                        ("+", None, 4, "    database_url: str = Field(env='DATABASE_URL', default='postgres://localhost/db')\n"),
                        (" ", 5, 5, "\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "DATABASE_URL"
        assert "postgres" in changed[0].new

    def test_extract_pydantic_added_field(self):
        """Test detecting added pydantic field."""
        old_src = """
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    database_url: str = Field(env='DATABASE_URL')
"""
        new_src = """
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    database_url: str = Field(env='DATABASE_URL')
    new_field: str = Field(env='NEW_FIELD')
"""

        fc = FileChange(
            old_path="settings.py",
            new_path="settings.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=5,
                    new_start=1,
                    new_len=6,
                    lines=[
                        (" ", 1, 1, "from pydantic import BaseSettings, Field\n"),
                        (" ", 2, 2, "\n"),
                        (" ", 3, 3, "class Settings(BaseSettings):\n"),
                        (" ", 4, 4, "    database_url: str = Field(env='DATABASE_URL')\n"),
                        ("+", None, 5, "    new_field: str = Field(env='NEW_FIELD')\n"),
                        (" ", 5, 6, "\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].symbol == "NEW_FIELD"

    # ===== Mixed patterns =====

    def test_extract_mixed_patterns(self):
        """Test detecting multiple patterns in one file."""
        src = """
import os
from os import environ
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    db_url: str = Field(env='DATABASE_URL')

def get_config():
    return {
        'host': environ['HOST'],
        'port': os.environ.get('PORT'),
        'timeout': os.getenv('TIMEOUT', '30'),
    }
"""
        symbols = self.extractor._extract_symbols(src)
        names = {s.name for s in symbols.values()}
        assert "DATABASE_URL" in names
        assert "HOST" in names
        assert "PORT" in names
        assert "TIMEOUT" in names

    # ===== Hunk intersection tests =====

    def test_ignores_changes_outside_hunks(self):
        """Test that changes outside diff hunks are ignored."""
        old_src = """import os
url = os.getenv('DATABASE_URL')
key = os.getenv('API_KEY')
"""
        new_src = """import os
url = os.getenv('DATABASE_URL', 'postgres://localhost/db')
key = os.getenv('API_KEY')
"""

        # Hunk only covers the first getenv (line 2)
        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=2,
                    old_len=1,
                    new_start=2,
                    new_len=1,
                    lines=[
                        ("-", 2, None, "url = os.getenv('DATABASE_URL')\n"),
                        ("+", None, 2, "url = os.getenv('DATABASE_URL', 'postgres://localhost/db')\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        # Should only detect DATABASE_URL change
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(changed) == 1
        assert changed[0].symbol == "DATABASE_URL"

    # ===== Edge cases =====

    def test_extract_empty_file(self):
        """Test extracting from empty file."""
        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="added",
            hunks=[],
        )

        facts = self.extractor.extract(fc, None, "import os\nurl = os.getenv('DATABASE_URL')\n")
        assert len(facts) == 0  # No hunks, so no facts

    def test_extract_removed_file(self):
        """Test extracting from removed file."""
        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="removed",
            hunks=[],
        )

        facts = self.extractor.extract(fc, "import os\nurl = os.getenv('DATABASE_URL')\n", None)
        assert len(facts) == 0  # No hunks, so no facts

    def test_extract_malformed_python(self):
        """Test handling malformed Python files."""
        old_src = "import os\nurl = os.getenv('DATABASE_URL'\n"  # Missing closing paren
        new_src = "import os\nurl = os.getenv('DATABASE_URL')\n"

        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "import os\n"),
                        ("-", 2, None, "url = os.getenv('DATABASE_URL'\n"),
                        ("+", None, 2, "url = os.getenv('DATABASE_URL')\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        # Malformed old code parses as empty, so new env var appears as added
        added = [f for f in facts if f.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].symbol == "DATABASE_URL"

    def test_extract_fact_structure(self):
        """Test that extracted facts have correct structure."""
        old_src = "import os\nurl = os.getenv('DATABASE_URL')\n"
        new_src = "import os\nurl = os.getenv('DATABASE_URL', 'postgres://localhost/db')\n"

        fc = FileChange(
            old_path="config.py",
            new_path="config.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "import os\n"),
                        ("-", 2, None, "url = os.getenv('DATABASE_URL')\n"),
                        ("+", None, 2, "url = os.getenv('DATABASE_URL', 'postgres://localhost/db')\n"),
                    ],
                )
            ],
        )

        facts = self.extractor.extract(fc, old_src, new_src)
        changed = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]

        assert len(changed) == 1
        fact = changed[0]
        # ID is assigned later in pipeline (_assign_ids), so we check other fields
        assert fact.symbol == "DATABASE_URL"
        assert fact.kind == SymbolKind.ENV_VAR
        assert fact.change_type == ChangeType.DEFAULT_CHANGED
        assert fact.location.path == "config.py"
        assert fact.extractor == "py_env"
        assert fact.public is True
        assert isinstance(fact.aliases, list)
        assert isinstance(fact.related, list)

    # ===== f-string and variable env names (not supported) =====

    def test_fstring_env_name_not_extracted(self):
        """Test that f-string env names are not extracted (dynamic)."""
        src = "import os\nvar = 'DATABASE_URL'\nurl = os.getenv(f'{var}')\n"
        symbols = self.extractor._extract_symbols(src)
        # f-strings are dynamic, we can't statically determine the value
        assert len(symbols) == 0

    def test_variable_env_name_not_extracted(self):
        """Test that variable env names are not extracted."""
        src = "import os\nvar = 'DATABASE_URL'\nurl = os.getenv(var)\n"
        symbols = self.extractor._extract_symbols(src)
        # Variables are dynamic, we can't statically determine the value
        assert len(symbols) == 0


class TestEnvExtractorAdditionalPatterns:
    """Test additional edge cases and patterns."""

    def setup_method(self):
        self.extractor = EnvExtractor()

    def test_extract_os_environ_direct_access(self):
        """Test os.environ['VAR'] direct access."""
        src = "import os\nvalue = os.environ['MY_VAR']\n"
        symbols = self.extractor._extract_symbols(src)
        assert len(symbols) == 1
        assert list(symbols.values())[0].name == "MY_VAR"

    def test_extract_environ_with_alias(self):
        """Test environ with alias import."""
        src = "from os import environ as env\nvalue = env['MY_VAR']\n"
        symbols = self.extractor._extract_symbols(src)
        assert len(symbols) == 1
        assert list(symbols.values())[0].name == "MY_VAR"

    def test_extract_getenv_with_multiple_args(self):
        """Test getenv with multiple arguments."""
        src = "import os\nurl = os.getenv('DATABASE_URL', 'default', 'encoding')\n"
        symbols = self.extractor._extract_symbols(src)
        assert len(symbols) == 1
        sym = list(symbols.values())[0]
        assert sym.name == "DATABASE_URL"
        assert sym.default_value == "'default'"
        assert "'encoding'" in sym.call_args

    def test_extract_no_duplicate_same_line(self):
        """Test that same env var on same line isn't duplicated."""
        src = "import os\nurl = os.getenv('DATABASE_URL'); key = os.getenv('DATABASE_URL')\n"
        symbols = self.extractor._extract_symbols(src)
        # Should have one entry per unique (name, kind, line)
        assert len(symbols) == 1

    def test_extract_base_model_class(self):
        """Test that BaseModel classes are also detected."""
        src = """
from pydantic import BaseModel, Field

class Config(BaseModel):
    api_key: str = Field(env='API_KEY')
"""
        symbols = self.extractor._extract_symbols(src)
        assert len(symbols) == 1
        assert list(symbols.values())[0].name == "API_KEY"

    def test_extract_nested_class_not_confused(self):
        """Test that nested classes don't confuse the extractor."""
        src = """
from pydantic import BaseSettings, Field

class Outer:
    class Settings(BaseSettings):
        api_key: str = Field(env='API_KEY')
"""
        symbols = self.extractor._extract_symbols(src)
        assert len(symbols) == 1
        assert list(symbols.values())[0].name == "API_KEY"


# Need to import EnvSymbol at module level for type hints
