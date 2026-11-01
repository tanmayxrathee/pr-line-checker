"""Environment variable extractor for os.getenv, os.environ, pydantic-settings."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from driftcheck.extract.base import FileChange, Hunk
from driftcheck.models import ChangeFact, ChangeType, CodeLocation, SymbolKind


@dataclass
class EnvSymbol:
    """Represents an environment variable access in source code."""

    name: str  # Variable name (e.g., "DATABASE_URL")
    kind: str  # "getenv", "environ", "pydantic_field", "dotenv"
    line: int  # Line number in source
    default_value: str | None  # Default value if provided
    call_args: tuple[str, ...]  # Additional call arguments

    def signature_key(self) -> tuple:
        """Return a key for matching env vars across versions."""
        return (self.name, self.kind)


class EnvExtractor:
    """Extract environment variable accesses from Python source code."""

    name = "py_env"

    def applies_to(self, path: str) -> bool:
        """Check if this extractor applies to the given file path."""
        return Path(path).suffix == ".py"

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        """Extract environment variable changes from a file change."""
        facts: list[ChangeFact] = []

        if not old_src and not new_src:
            return facts

        # Build symbol tables for both versions
        old_symbols = self._extract_symbols(old_src) if old_src else {}
        new_symbols = self._extract_symbols(new_src) if new_src else {}

        # Match symbols by env var name (primary key)
        # Build lookup by env var name
        old_by_name: dict[str, EnvSymbol] = {}
        for key, sym in old_symbols.items():
            if sym.name not in old_by_name:
                old_by_name[sym.name] = sym

        new_by_name: dict[str, EnvSymbol] = {}
        for key, sym in new_symbols.items():
            if sym.name not in new_by_name:
                new_by_name[sym.name] = sym

        # Find added, removed, and changed env vars
        all_names = set(old_by_name.keys()) | set(new_by_name.keys())

        for name in all_names:
            old_sym = old_by_name.get(name)
            new_sym = new_by_name.get(name)

            if old_sym is None and new_sym is not None:
                # Added
                fact = self._make_fact(
                    fc=fc,
                    symbol=new_sym,
                    change_type=ChangeType.ADDED,
                    old=None,
                    new=self._symbol_value(new_sym),
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
                    old=self._symbol_value(old_sym),
                    new=None,
                    line_old=old_sym.line,
                    line_new=None,
                )
                if fact and self._intersects_hunks(fact, fc.hunks):
                    facts.append(fact)

            elif old_sym is not None and new_sym is not None:
                # Modified - check for changes in default value or kind
                if (old_sym.default_value != new_sym.default_value
                        or old_sym.kind != new_sym.kind
                        or old_sym.call_args != new_sym.call_args):
                    fact = self._make_fact(
                        fc=fc,
                        symbol=new_sym,
                        change_type=ChangeType.DEFAULT_CHANGED,
                        old=self._symbol_value(old_sym),
                        new=self._symbol_value(new_sym),
                        line_old=old_sym.line,
                        line_new=new_sym.line,
                    )
                    if fact and self._intersects_hunks(fact, fc.hunks):
                        facts.append(fact)

        return facts

    def _extract_symbols(self, source: str) -> dict[str, EnvSymbol]:
        """Extract all environment variable symbols from source code."""
        symbols: dict[str, EnvSymbol] = {}

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return symbols

        visitor = EnvVisitor(source)
        visitor.visit(tree)

        for sym in visitor.symbols:
            # Use the variable name as the key, deduplicate by (name, kind, line)
            key = f"{sym.name}:{sym.kind}:{sym.line}"
            # Keep the first occurrence (or the one with more info)
            if key not in symbols:
                symbols[key] = sym

        return symbols

    def _symbol_value(self, sym: EnvSymbol) -> str:
        """Get a string representation of the symbol for diffing."""
        parts = [sym.kind]
        if sym.default_value is not None:
            parts.append(f"default={sym.default_value}")
        if sym.call_args:
            parts.append(f"args={sym.call_args}")
        return " ".join(parts)

    def _make_fact(
        self,
        fc: FileChange,
        symbol: EnvSymbol,
        change_type: ChangeType,
        old: str | None,
        new: str | None,
        line_old: int | None,
        line_new: int | None,
    ) -> ChangeFact | None:
        """Create a ChangeFact from an EnvSymbol."""
        code_snippet = self._get_code_snippet(fc.hunks, line_old, line_new)

        location = CodeLocation(
            path=fc.path,
            line_old=line_old,
            line_new=line_new,
        )

        return ChangeFact(
            id="",
            symbol=symbol.name,
            kind=SymbolKind.ENV_VAR,
            change_type=change_type,
            old=old,
            new=new,
            aliases=[symbol.name],
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
                if new_no and abs(new_no - target_line) <= 2:
                    prefix = "+" if tag == "+" else ("-" if tag == "-" else " ")
                    lines.append(f"{prefix}{text.rstrip()}")
                elif old_no and abs(old_no - target_line) <= 2:
                    prefix = "+" if tag == "+" else ("-" if tag == "-" else " ")
                    lines.append(f"{prefix}{text.rstrip()}")

        return "\n".join(lines[:10])


class EnvVisitor(ast.NodeVisitor):
    """AST visitor to find environment variable accesses."""

    def __init__(self, source: str):
        self.source = source
        self.lines = source.splitlines()
        self.symbols: list[EnvSymbol] = []
        self._imported_names: set[str] = set()  # Track imported names like getenv, environ

    def visit_Import(self, node: ast.Import) -> None:
        """Track imported modules."""
        for alias in node.names:
            if alias.name == "os":
                self._imported_names.add("os")
            elif alias.name == "os.environ":
                self._imported_names.add("environ")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track imported names from modules."""
        if node.module == "os":
            for alias in node.names:
                if alias.name in ("getenv", "environ"):
                    # Track both the original name and the alias (if any)
                    self._imported_names.add(alias.name)
                    if alias.asname:
                        self._imported_names.add(alias.asname)
        elif node.module == "os.path":
            pass  # Not relevant for env vars
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function calls to find env var accesses."""
        # Check for os.getenv("VAR") or getenv("VAR")
        if self._is_getenv_call(node):
            self._extract_getenv(node)
        # Check for os.environ["VAR"] or os.environ.get("VAR")
        elif self._is_environ_access(node):
            self._extract_environ(node)
        # Check for pydantic Field(env="VAR")
        elif self._is_pydantic_field(node):
            self._extract_pydantic_field(node)
        # Check for dotenv/load_dotenv patterns
        elif self._is_dotenv_call(node):
            self._extract_dotenv(node)

        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Visit subscript access like environ['VAR']."""
        # Check for direct environ['VAR'] access
        if self._is_environ_subscript(node):
            self._extract_environ_subscript(node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute access for pydantic Settings classes."""
        # Check for class attributes with Field(env="VAR")
        if isinstance(node.value, ast.Name) and node.attr in ("model_fields", "__fields__"):
            pass  # Handled in class visit
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definitions for pydantic Settings."""
        # Check if this is a pydantic BaseSettings or similar
        if self._is_pydantic_settings_class(node):
            self._extract_pydantic_settings(node)
        self.generic_visit(node)

    def _is_getenv_call(self, node: ast.Call) -> bool:
        """Check if this is a getenv call."""
        if isinstance(node.func, ast.Name):
            return node.func.id in ("getenv", "os_getenv") and "getenv" in self._imported_names
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return (node.func.value.id == "os" and node.func.attr == "getenv") or \
                       (node.func.value.id in self._imported_names and node.func.attr == "getenv")
        return False

    def _extract_getenv(self, node: ast.Call) -> None:
        """Extract env var from getenv call."""
        if not node.args:
            return

        # First argument is the variable name
        name = self._get_string_value(node.args[0])
        if not name:
            return

        # Second argument (optional) is default value
        default = None
        if len(node.args) > 1:
            default = self._unparse(node.args[1])

        # Additional args (like encoding in some implementations)
        call_args = tuple(self._unparse(arg) for arg in node.args[2:])

        self.symbols.append(EnvSymbol(
            name=name,
            kind="getenv",
            line=node.lineno,
            default_value=default,
            call_args=call_args,
        ))

    def _is_environ_access(self, node: ast.Call) -> bool:
        """Check if this is an environ.get() call."""
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "get":
                # Check if it's environ.get or os.environ.get
                if isinstance(node.func.value, ast.Name):
                    return node.func.value.id in self._imported_names
                if isinstance(node.func.value, ast.Attribute):
                    if (isinstance(node.func.value.value, ast.Name)
                            and node.func.value.value.id == "os"
                            and node.func.value.attr == "environ"):
                        return True
        return False

    def _extract_environ(self, node: ast.Call) -> None:
        """Extract env var from environ.get() call."""
        if not node.args:
            return

        name = self._get_string_value(node.args[0])
        if not name:
            return

        default = None
        if len(node.args) > 1:
            default = self._unparse(node.args[1])

        call_args = tuple(self._unparse(arg) for arg in node.args[2:])

        self.symbols.append(EnvSymbol(
            name=name,
            kind="environ_get",
            line=node.lineno,
            default_value=default,
            call_args=call_args,
        ))

    def _is_environ_subscript(self, node: ast.Subscript) -> bool:
        """Check if this is a direct environ['VAR'] access."""
        if isinstance(node.value, ast.Name):
            return node.value.id in self._imported_names
        if isinstance(node.value, ast.Attribute):
            if (isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "os"
                    and node.value.attr == "environ"):
                return True
        return False

    def _extract_environ_subscript(self, node: ast.Subscript) -> None:
        """Extract env var from direct environ['VAR'] access."""
        # Get the key from the subscript
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            name = node.slice.value
        elif isinstance(node.slice, ast.Index) and isinstance(node.slice.value, ast.Constant):
            # Python 3.8 compatibility
            name = node.slice.value.value
        else:
            return

        if not name:
            return

        self.symbols.append(EnvSymbol(
            name=name,
            kind="environ",
            line=node.lineno,
            default_value=None,
            call_args=(),
        ))

    def _is_pydantic_field(self, node: ast.Call) -> bool:
        """Check if this is a pydantic Field() call with env parameter."""
        if isinstance(node.func, ast.Name):
            return node.func.id == "Field"
        if isinstance(node.func, ast.Attribute):
            return node.func.attr == "Field"
        return False

    def _extract_pydantic_field(self, node: ast.Call) -> None:
        """Extract env var from pydantic Field(env='VAR')."""
        # Look for env= keyword argument
        env_name = None
        default_value = None
        for keyword in node.keywords:
            if keyword.arg == "env":
                env_name = self._get_string_value(keyword.value)
            elif keyword.arg == "default":
                default_value = self._unparse(keyword.value)

        if env_name:
            self.symbols.append(EnvSymbol(
                name=env_name,
                kind="pydantic_field",
                line=node.lineno,
                default_value=default_value,
                call_args=("Field",),
            ))

    def _is_pydantic_settings_class(self, node: ast.ClassDef) -> bool:
        """Check if class inherits from pydantic BaseSettings."""
        for base in node.bases:
            if isinstance(base, ast.Name):
                if base.id in ("BaseSettings", "BaseModel"):
                    return True
            elif isinstance(base, ast.Attribute):
                if base.attr in ("BaseSettings", "BaseModel"):
                    return True
        return False

    def _extract_pydantic_settings(self, node: ast.ClassDef) -> None:
        """Extract env vars from pydantic Settings class fields."""
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                # Annotated assignment: VAR_NAME: type = Field(...)
                field_name = item.target.id
                # Check if it has a Field default with env
                if item.value and isinstance(item.value, ast.Call):
                    env_name = None
                    default_value = None
                    for keyword in item.value.keywords:
                        if keyword.arg == "env":
                            env_name = self._get_string_value(keyword.value)
                        elif keyword.arg == "default":
                            default_value = self._unparse(keyword.value)

                    if env_name:
                        self.symbols.append(EnvSymbol(
                            name=env_name,
                            kind="pydantic_field",
                            line=item.lineno,
                            default_value=default_value,
                            call_args=(f"field={field_name}",),
                        ))

    def _is_dotenv_call(self, node: ast.Call) -> bool:
        """Check for dotenv related calls."""
        if isinstance(node.func, ast.Name):
            return node.func.id in ("load_dotenv", "dotenv_values")
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in ("load_dotenv", "get", "values")
        return False

    def _extract_dotenv(self, node: ast.Call) -> None:
        """Extract from dotenv calls - usually not specific vars, but we can note usage."""
        # dotenv typically loads all vars from .env file, so we don't extract specific names
        # unless they're accessed via the returned dict
        pass

    def _get_string_value(self, node: ast.AST) -> str | None:
        """Extract string value from a node if it's a constant string."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            # f-string - try to extract if it's simple
            if len(node.values) == 1 and isinstance(node.values[0], ast.Constant):
                return node.values[0].value
        return None

    def _unparse(self, node: ast.AST) -> str:
        """Convert AST node back to source code string."""
        try:
            return ast.unparse(node)
        except Exception:
            return "<unparseable>"
