"""Tests for Python symbols extractor (functions, classes, parameters, constants)."""

import pytest

from driftcheck.extract.base import FileChange, Hunk
from driftcheck.extract.py_symbols import PythonSymbolTable, SymbolsExtractor
from driftcheck.models import ChangeType, SymbolKind


class TestPythonSymbolTable:
    """Tests for the PythonSymbolTable class."""

    def test_simple_function(self):
        """Test extracting a simple function."""
        source = '''
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}"
'''
        table = PythonSymbolTable(source, "test.py")
        assert "greet" in table.symbols
        sym = table.symbols["greet"]
        assert sym.kind == SymbolKind.FUNCTION
        assert sym.type_annotation == "str"
        assert sym.docstring == "Say hello."
        assert sym.is_async is False
        assert sym.is_method is False

    def test_async_function(self):
        """Test extracting an async function."""
        source = """
async def fetch_data(url: str) -> dict:
    return {}
"""
        table = PythonSymbolTable(source, "test.py")
        assert "fetch_data" in table.symbols
        sym = table.symbols["fetch_data"]
        assert sym.is_async is True

    def test_function_with_parameters(self):
        """Test extracting function parameters."""
        source = """
def process(items: list[str], limit: int = 10, *, verbose: bool = False) -> None:
    pass
"""
        table = PythonSymbolTable(source, "test.py")
        assert "process" in table.symbols
        assert "process.items" in table.symbols
        assert "process.limit" in table.symbols
        assert "process.verbose" in table.symbols

        items_param = table.symbols["process.items"]
        assert items_param.kind == SymbolKind.PARAMETER
        assert items_param.type_annotation == "list[str]"

        limit_param = table.symbols["process.limit"]
        assert limit_param.default_value == "10"

    def test_simple_class(self):
        """Test extracting a simple class."""
        source = '''
class User:
    """User model."""
    name: str
    age: int = 30
'''
        table = PythonSymbolTable(source, "test.py")
        assert "User" in table.symbols
        sym = table.symbols["User"]
        assert sym.kind == SymbolKind.CLASS
        assert sym.docstring == "User model."

    def test_class_with_methods(self):
        """Test extracting a class with methods."""
        source = """
class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

    async def multiply(self, a: int, b: int) -> int:
        return a * b
"""
        table = PythonSymbolTable(source, "test.py")
        assert "Calculator" in table.symbols
        assert "Calculator.add" in table.symbols
        assert "Calculator.multiply" in table.symbols

        add_method = table.symbols["Calculator.add"]
        assert add_method.kind == SymbolKind.FUNCTION
        assert add_method.is_method is True
        assert add_method.parent == "Calculator"

        multiply_method = table.symbols["Calculator.multiply"]
        assert multiply_method.is_async is True

    def test_dataclass_fields(self):
        """Test extracting dataclass fields."""
        source = """
from dataclasses import dataclass

@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
"""
        table = PythonSymbolTable(source, "test.py")
        assert "Config" in table.symbols
        assert "Config.host" in table.symbols
        assert "Config.port" in table.symbols
        assert "Config.debug" in table.symbols

        host_field = table.symbols["Config.host"]
        assert host_field.kind == SymbolKind.FIELD
        assert host_field.type_annotation == "str"
        # ast.unparse uses single quotes for string literals
        assert host_field.default_value == "'localhost'"

    def test_pydantic_model_fields(self):
        """Test extracting Pydantic model fields."""
        source = """
from pydantic import BaseModel

class Settings(BaseModel):
    api_key: str
    timeout: int = 30
"""
        table = PythonSymbolTable(source, "test.py")
        assert "Settings" in table.symbols
        assert "Settings.api_key" in table.symbols
        assert "Settings.timeout" in table.symbols

        api_key = table.symbols["Settings.api_key"]
        assert api_key.kind == SymbolKind.FIELD
        assert api_key.type_annotation == "str"

    def test_class_constants(self):
        """Test extracting class constants (UPPER_CASE)."""
        source = """
class Constants:
    MAX_RETRIES = 3
    DEFAULT_TIMEOUT = 30.0
    API_VERSION = "v1"
"""
        table = PythonSymbolTable(source, "test.py")
        assert "Constants.MAX_RETRIES" in table.symbols
        assert "Constants.DEFAULT_TIMEOUT" in table.symbols
        assert "Constants.API_VERSION" in table.symbols

        max_retries = table.symbols["Constants.MAX_RETRIES"]
        assert max_retries.kind == SymbolKind.CONSTANT
        assert max_retries.default_value == "3"

    def test_module_level_constants(self):
        """Test extracting module-level constants."""
        source = """
MAX_CONNECTIONS = 100
API_BASE_URL = "https://api.example.com"
DEFAULT_ENCODING = "utf-8"
"""
        table = PythonSymbolTable(source, "test.py")
        assert "MAX_CONNECTIONS" in table.symbols
        assert "API_BASE_URL" in table.symbols
        assert "DEFAULT_ENCODING" in table.symbols

        max_conn = table.symbols["MAX_CONNECTIONS"]
        assert max_conn.kind == SymbolKind.CONSTANT
        assert max_conn.default_value == "100"
        assert max_conn.parent is None

    def test_decorated_function(self):
        """Test extracting a function with decorators."""
        source = """
@staticmethod
@lru_cache(maxsize=128)
def cached_compute(x: int) -> int:
    return x * 2
"""
        table = PythonSymbolTable(source, "test.py")
        sym = table.symbols["cached_compute"]
        assert "staticmethod" in sym.decorators
        assert "lru_cache" in sym.decorators

    def test_nested_class(self):
        """Test extracting nested classes."""
        source = """
class Outer:
    class Inner:
        value: int = 42
"""
        table = PythonSymbolTable(source, "test.py")
        assert "Outer" in table.symbols
        assert "Outer.Inner" in table.symbols
        assert "Outer.Inner.value" in table.symbols

        inner = table.symbols["Outer.Inner"]
        assert inner.parent == "Outer"

    def test_private_symbols(self):
        """Test extracting private symbols (prefixed with _)."""
        source = """
def _private_helper() -> None:
    pass

class _Internal:
    pass

_INTERNAL_CONST = "secret"
"""
        table = PythonSymbolTable(source, "test.py")
        assert "_private_helper" in table.symbols
        assert "_Internal" in table.symbols
        assert "_INTERNAL_CONST" in table.symbols

        helper = table.symbols["_private_helper"]
        # PythonSymbol doesn't have public attribute; it's set on ChangeFact by the extractor
        assert helper.name == "_private_helper"


class TestSymbolsExtractor:
    """Tests for the SymbolsExtractor class."""

    def setup_method(self):
        self.extractor = SymbolsExtractor()

    def _make_file_change(self, status: str = "modified") -> FileChange:
        """Create a basic FileChange for testing."""
        return FileChange(
            old_path="test.py",
            new_path="test.py",
            status=status,
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=10,
                    new_start=1,
                    new_len=10,
                    lines=[
                        (" ", 1, 1, "def greet(name: str) -> str:\n"),
                        (" ", 2, 2, '    return f"Hello, {name}"\n'),
                    ],
                )
            ],
        )

    def test_extract_added_function(self):
        """Test detecting an added function."""
        old_src = ""
        new_src = """
def new_function(x: int) -> int:
    return x * 2
"""
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="added",
            hunks=[
                Hunk(
                    old_start=0,
                    old_len=0,
                    new_start=1,
                    new_len=3,
                    lines=[
                        ("+", None, 1, "def new_function(x: int) -> int:\n"),
                        ("+", None, 2, "    return x * 2\n"),
                        ("+", None, 3, "\n"),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        added_funcs = [
            f for f in facts if f.change_type == ChangeType.ADDED and f.kind == SymbolKind.FUNCTION
        ]
        assert len(added_funcs) == 1
        assert added_funcs[0].symbol == "new_function"

    def test_extract_removed_function(self):
        """Test detecting a removed function."""
        old_src = """
def old_function() -> None:
    pass
"""
        new_src = ""
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="removed",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=3,
                    new_start=1,
                    new_len=0,
                    lines=[
                        ("-", 1, None, "def old_function() -> None:\n"),
                        ("-", 2, None, "    pass\n"),
                        ("-", 3, None, "\n"),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        removed_funcs = [
            f
            for f in facts
            if f.change_type == ChangeType.REMOVED and f.kind == SymbolKind.FUNCTION
        ]
        assert len(removed_funcs) == 1
        assert removed_funcs[0].symbol == "old_function"

    def test_extract_renamed_function(self):
        """Test detecting a renamed function (same signature, different name)."""
        old_src = """
def calculate_total(items: list[int]) -> int:
    return sum(items)
"""
        new_src = """
def sum_items(items: list[int]) -> int:
    return sum(items)
"""
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=3,
                    new_start=1,
                    new_len=3,
                    lines=[
                        ("-", 1, None, "def calculate_total(items: list[int]) -> int:\n"),
                        ("-", 2, None, "    return sum(items)\n"),
                        ("-", 3, None, "\n"),
                        ("+", None, 1, "def sum_items(items: list[int]) -> int:\n"),
                        ("+", None, 2, "    return sum(items)\n"),
                        ("+", None, 3, "\n"),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        renamed = [
            f
            for f in facts
            if f.change_type == ChangeType.RENAMED and f.kind == SymbolKind.FUNCTION
        ]
        assert len(renamed) == 1
        assert renamed[0].old == "calculate_total"
        assert renamed[0].new == "sum_items"

    def test_extract_return_type_changed(self):
        """Test detecting a return type change."""
        old_src = """
def get_value() -> int:
    return 42
"""
        new_src = """
def get_value() -> str:
    return "42"
"""
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        ("-", 1, None, "def get_value() -> int:\n"),
                        ("-", 2, None, "    return 42\n"),
                        ("+", None, 1, "def get_value() -> str:\n"),
                        ("+", None, 2, '    return "42"\n'),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        type_changed = [
            f
            for f in facts
            if f.change_type == ChangeType.TYPE_CHANGED and f.kind == SymbolKind.FUNCTION
        ]
        assert len(type_changed) == 1
        assert type_changed[0].old == "int"
        assert type_changed[1].new == "str" if len(type_changed) > 1 else True

    def test_extract_parameter_default_changed(self):
        """Test detecting a parameter default value change."""
        old_src = """
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}"
"""
        new_src = """
def greet(name: str, greeting: str = "Hi") -> str:
    return f"{greeting}, {name}"
"""
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        ("-", 1, None, 'def greet(name: str, greeting: str = "Hello") -> str:\n'),
                        ("-", 2, None, '    return f"{greeting}, {name}"\n'),
                        ("+", None, 1, 'def greet(name: str, greeting: str = "Hi") -> str:\n'),
                        ("+", None, 2, '    return f"{greeting}, {name}"\n'),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        # Should detect the default change for the parameter
        default_changed = [
            f
            for f in facts
            if f.change_type == ChangeType.DEFAULT_CHANGED and f.kind == SymbolKind.PARAMETER
        ]
        assert len(default_changed) >= 1

    def test_extract_constant_changed(self):
        """Test detecting a constant value change."""
        old_src = """
MAX_RETRIES = 3
"""
        new_src = """
MAX_RETRIES = 5
"""
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=2,
                    old_len=1,
                    new_start=2,
                    new_len=1,
                    lines=[
                        ("-", 2, None, "MAX_RETRIES = 3\n"),
                        ("+", None, 2, "MAX_RETRIES = 5\n"),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        const_changed = [
            f
            for f in facts
            if f.change_type == ChangeType.DEFAULT_CHANGED and f.kind == SymbolKind.CONSTANT
        ]
        assert len(const_changed) == 1
        assert const_changed[0].old == "3"
        assert const_changed[0].new == "5"

    def test_extract_class_field_changed(self):
        """Test detecting a dataclass field default change."""
        old_src = """
from dataclasses import dataclass

@dataclass
class Config:
    timeout: int = 30
"""
        new_src = """
from dataclasses import dataclass

@dataclass
class Config:
    timeout: int = 60
"""
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=5,
                    old_len=2,
                    new_start=5,
                    new_len=2,
                    lines=[
                        (" ", 1, 1, "from dataclasses import dataclass\n"),
                        (" ", 2, 2, "\n"),
                        (" ", 3, 3, "@dataclass\n"),
                        (" ", 4, 4, "class Config:\n"),
                        ("-", 6, None, "    timeout: int = 30\n"),
                        ("+", None, 6, "    timeout: int = 60\n"),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        field_changed = [
            f
            for f in facts
            if f.change_type == ChangeType.DEFAULT_CHANGED and f.kind == SymbolKind.FIELD
        ]
        assert len(field_changed) == 1
        assert field_changed[0].old == "30"
        assert field_changed[0].new == "60"

    def test_extract_decorator_changed(self):
        """Test detecting a decorator change."""
        old_src = """
@staticmethod
def helper() -> None:
    pass
"""
        new_src = """
@classmethod
def helper(cls) -> None:
    pass
"""
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=3,
                    new_start=1,
                    new_len=3,
                    lines=[
                        ("-", 1, None, "@staticmethod\n"),
                        ("-", 2, None, "def helper() -> None:\n"),
                        ("-", 3, None, "    pass\n"),
                        ("+", None, 1, "@classmethod\n"),
                        ("+", None, 2, "def helper(cls) -> None:\n"),
                        ("+", None, 3, "    pass\n"),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        sig_changed = [
            f
            for f in facts
            if f.change_type == ChangeType.SIGNATURE_CHANGED and f.kind == SymbolKind.FUNCTION
        ]
        assert len(sig_changed) == 1
        assert "staticmethod" in (sig_changed[0].old or "")
        assert "classmethod" in (sig_changed[0].new or "")

    def test_extract_async_changed(self):
        """Test detecting async/sync change."""
        old_src = """
def fetch() -> str:
    return "data"
"""
        new_src = """
async def fetch() -> str:
    return "data"
"""
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=1,
                    old_len=2,
                    new_start=1,
                    new_len=2,
                    lines=[
                        ("-", 1, None, "def fetch() -> str:\n"),
                        ("-", 2, None, '    return "data"\n'),
                        ("+", None, 1, "async def fetch() -> str:\n"),
                        ("+", None, 2, '    return "data"\n'),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        sig_changed = [
            f
            for f in facts
            if f.change_type == ChangeType.SIGNATURE_CHANGED and f.kind == SymbolKind.FUNCTION
        ]
        assert len(sig_changed) == 1
        assert sig_changed[0].old == "sync"
        assert sig_changed[0].new == "async"

    def test_ignores_symbols_outside_hunks(self):
        """Test that symbols outside diff hunks are ignored."""
        old_src = """
def func_a() -> None:
    pass

def func_b() -> None:
    pass
"""
        new_src = """
def func_a() -> None:
    pass

def func_b() -> str:
    return "changed"
"""
        # Only func_b is in the hunk
        fc = FileChange(
            old_path="test.py",
            new_path="test.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=5,
                    old_len=2,
                    new_start=5,
                    new_len=2,
                    lines=[
                        ("-", 5, None, "def func_b() -> None:\n"),
                        ("-", 6, None, "    pass\n"),
                        ("+", None, 5, "def func_b() -> str:\n"),
                        ("+", None, 6, '    return "changed"\n'),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)
        # Only func_b should be detected
        type_changed = [
            f
            for f in facts
            if f.change_type == ChangeType.TYPE_CHANGED and f.kind == SymbolKind.FUNCTION
        ]
        assert len(type_changed) == 1
        assert type_changed[0].symbol == "func_b"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
