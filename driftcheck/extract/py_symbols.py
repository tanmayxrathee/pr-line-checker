"""Python symbols extractor for functions, classes, parameters, constants."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from driftcheck.extract.base import FileChange, Hunk
from driftcheck.models import ChangeFact, ChangeType, CodeLocation, SymbolKind


@dataclass
class PythonSymbol:
    """Represents a Python symbol extracted from source code."""

    name: str  # Simple name (e.g., "method" or "CONSTANT")
    kind: SymbolKind  # FUNCTION, CLASS, PARAMETER, CONSTANT, FIELD
    qualified_name: str  # Fully qualified name for matching across versions
    type_annotation: str | None  # Type annotation as source code
    default_value: str | None  # Default value as source code
    line: int  # Line number in source
    parent: str | None  # Parent class/function qualified name
    is_async: bool  # True for async functions
    is_method: bool  # True if this is a method (inside a class)
    decorators: list[str]  # List of decorator names
    docstring: str | None  # Docstring if present
    param_types: tuple[str, ...] = ()  # Parameter type annotations for functions

    def signature_key(self) -> tuple:
        """Return a key for matching symbols across versions."""
        return (
            self.kind,
            self.type_annotation,
            self.default_value,
            self.parent,
            self.is_async,
            tuple(self.decorators),
            self.param_types,
        )


class PythonSymbolTable:
    """Symbol table for Python symbols in a single source file."""

    def __init__(self, source: str, file_path: str):
        self.source = source
        self.file_path = file_path
        self.tree = ast.parse(source)
        self.symbols: dict[str, PythonSymbol] = {}  # qualified_name -> PythonSymbol
        self._extract_symbols()

    def _extract_symbols(self) -> None:
        """Walk the AST and extract all Python symbols."""
        # Extract module-level constants first
        self._extract_module_constants()

        # Then extract classes and functions
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_function(node, parent=None)
            elif isinstance(node, ast.ClassDef):
                self._extract_class(node, parent=None)

    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent: str | None,
    ) -> None:
        """Extract a function or method."""
        qualified_name = self._build_qualified_name(node.name, parent)
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)

        # Determine if this is a method (inside a class)
        is_method = parent is not None

        # Extract parameters with their default values
        params = self._extract_parameters(node.args, qualified_name)

        # Collect parameter types for signature key
        param_types = tuple(
            self._unparse(arg.annotation) if arg.annotation else "" for arg in node.args.args
        )
        param_types += tuple(
            self._unparse(arg.annotation) if arg.annotation else "" for arg in node.args.kwonlyargs
        )
        if node.args.vararg and node.args.vararg.annotation:
            param_types += (self._unparse(node.args.vararg.annotation),)
        if node.args.kwarg and node.args.kwarg.annotation:
            param_types += (self._unparse(node.args.kwarg.annotation),)

        # Add the function itself
        symbol = PythonSymbol(
            name=node.name,
            kind=SymbolKind.FUNCTION,
            qualified_name=qualified_name,
            type_annotation=self._get_return_annotation(node),
            default_value=None,
            line=node.lineno,
            parent=parent,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=is_method,
            decorators=decorators,
            docstring=docstring,
            param_types=param_types,
        )
        self.symbols[qualified_name] = symbol

        # Add parameters as separate symbols
        for param in params:
            self.symbols[param.qualified_name] = param

    def _extract_class(self, node: ast.ClassDef, parent: str | None) -> None:
        """Extract a class and its members."""
        qualified_name = self._build_qualified_name(node.name, parent)
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)

        # Check if it's a dataclass
        is_dataclass = any(d in ("dataclass", "dataclass_transform") for d in decorators)

        # Check if it's a Pydantic model (inherits from BaseModel)
        is_pydantic = self._is_pydantic_model(node)

        # Add the class itself
        symbol = PythonSymbol(
            name=node.name,
            kind=SymbolKind.CLASS,
            qualified_name=qualified_name,
            type_annotation=None,
            default_value=None,
            line=node.lineno,
            parent=parent,
            is_async=False,
            is_method=False,
            decorators=decorators,
            docstring=docstring,
        )
        self.symbols[qualified_name] = symbol

        # Extract class body
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_function(item, parent=qualified_name)
            elif isinstance(item, ast.ClassDef):
                # Handle nested classes
                self._extract_class(item, parent=qualified_name)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                # Class attribute with type annotation (field)
                self._extract_class_field(item, qualified_name, is_dataclass, is_pydantic)
            elif isinstance(item, ast.Assign):
                # Class attribute assignment (could be constant)
                self._extract_class_assignment(item, qualified_name)

    def _is_pydantic_model(self, node: ast.ClassDef) -> bool:
        """Check if a class is a Pydantic model."""
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "BaseModel":
                return True
            elif isinstance(base, ast.Attribute):
                # Handle pydantic.BaseModel
                if base.attr == "BaseModel":
                    return True
        return False

    def _extract_parameters(
        self,
        args: ast.arguments,
        parent_qualified: str,
    ) -> list[PythonSymbol]:
        """Extract function parameters with their default values."""
        params = []

        # Collect all args in order
        all_args = []
        all_args.extend(args.posonlyargs)
        all_args.extend(args.args)
        if args.vararg:
            all_args.append(args.vararg)
        all_args.extend(args.kwonlyargs)
        if args.kwarg:
            all_args.append(args.kwarg)

        # Map argument index to default value
        # defaults correspond to the last N positional args
        num_positional = len(args.posonlyargs) + len(args.args)
        num_defaults = len(args.defaults)
        default_start = num_positional - num_defaults

        # kw_defaults correspond to keyword-only args
        kw_default_map = {}
        for i, kw_default in enumerate(args.kw_defaults):
            if kw_default and i < len(args.kwonlyargs):
                kw_default_map[args.kwonlyargs[i].arg] = kw_default

        for idx, arg in enumerate(all_args):
            # Check if this arg has a default
            default_value = None
            if idx >= default_start and idx < num_positional:
                default_idx = idx - default_start
                if default_idx < len(args.defaults):
                    default_value = args.defaults[default_idx]
            elif arg.arg in kw_default_map:
                default_value = kw_default_map[arg.arg]

            params.append(self._make_parameter(arg, parent_qualified, default_value))

        return params

    def _make_parameter(
        self,
        arg: ast.arg,
        parent_qualified: str,
        default_node: ast.expr | None,
    ) -> PythonSymbol:
        """Create a parameter symbol."""
        qualified_name = f"{parent_qualified}.{arg.arg}"
        type_ann = self._unparse(arg.annotation) if arg.annotation else None
        default = self._unparse(default_node) if default_node else None

        return PythonSymbol(
            name=arg.arg,
            kind=SymbolKind.PARAMETER,
            qualified_name=qualified_name,
            type_annotation=type_ann,
            default_value=default,
            line=getattr(arg, "lineno", 1),
            parent=parent_qualified,
            is_async=False,
            is_method=False,
            decorators=[],
            docstring=None,
        )

    def _extract_class_field(
        self,
        node: ast.AnnAssign,
        parent_qualified: str,
        is_dataclass: bool,
        is_pydantic: bool,
    ) -> None:
        """Extract a class field (dataclass/pydantic field or typed attribute)."""
        target = node.target
        if not isinstance(target, ast.Name):
            return

        qualified_name = f"{parent_qualified}.{target.id}"
        type_ann = self._unparse(node.annotation) if node.annotation else None
        default = self._unparse(node.value) if node.value else None

        # Determine if this is a field vs constant
        kind = SymbolKind.FIELD if (is_dataclass or is_pydantic) else SymbolKind.CONSTANT

        # If it's ALL_CAPS, treat as constant
        if target.id.isupper():
            kind = SymbolKind.CONSTANT

        symbol = PythonSymbol(
            name=target.id,
            kind=kind,
            qualified_name=qualified_name,
            type_annotation=type_ann,
            default_value=default,
            line=node.lineno,
            parent=parent_qualified,
            is_async=False,
            is_method=False,
            decorators=[],
            docstring=None,
        )
        self.symbols[qualified_name] = symbol

    def _extract_class_assignment(
        self,
        node: ast.Assign,
        parent_qualified: str,
    ) -> None:
        """Extract class-level assignments (constants, class attributes)."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                qualified_name = f"{parent_qualified}.{target.id}"
                value = self._unparse(node.value)

                # Determine kind: CONSTANT if UPPER_CASE, otherwise FIELD
                kind = SymbolKind.CONSTANT if target.id.isupper() else SymbolKind.FIELD

                symbol = PythonSymbol(
                    name=target.id,
                    kind=kind,
                    qualified_name=qualified_name,
                    type_annotation=None,
                    default_value=value,
                    line=node.lineno,
                    parent=parent_qualified,
                    is_async=False,
                    is_method=False,
                    decorators=[],
                    docstring=None,
                )
                self.symbols[qualified_name] = symbol

    def _extract_module_constants(self) -> None:
        """Extract module-level constants (UPPER_CASE assignments)."""
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        qualified_name = target.id
                        value = self._unparse(node.value)
                        symbol = PythonSymbol(
                            name=target.id,
                            kind=SymbolKind.CONSTANT,
                            qualified_name=qualified_name,
                            type_annotation=None,
                            default_value=value,
                            line=node.lineno,
                            parent=None,
                            is_async=False,
                            is_method=False,
                            decorators=[],
                            docstring=None,
                        )
                        self.symbols[qualified_name] = symbol

    def _build_qualified_name(self, name: str, parent: str | None) -> str:
        """Build a fully qualified name."""
        if parent:
            return f"{parent}.{name}"
        return name

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Get the name of a decorator."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr
        elif isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        return ""

    def _get_return_annotation(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        """Get the return type annotation."""
        if node.returns:
            return self._unparse(node.returns)
        return None

    def _unparse(self, node: ast.AST) -> str:
        """Safely unparse an AST node to source code."""
        try:
            return ast.unparse(node)
        except Exception:
            return ""


class SymbolsExtractor:
    """Extract Python symbols (functions, classes, params, constants)."""

    name = "py_symbols"

    def applies_to(self, path: str) -> bool:
        return path.endswith(".py")

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        """Extract Python symbol changes from a file change."""
        facts: list[ChangeFact] = []

        # Build symbol tables for both versions
        old_table = PythonSymbolTable(old_src, fc.old_path) if old_src else None
        new_table = PythonSymbolTable(new_src, fc.new_path) if new_src else None

        # Get all symbols from both tables
        old_symbols = old_table.symbols if old_table else {}
        new_symbols = new_table.symbols if new_table else {}

        # First, match by qualified_name (same symbol, potentially modified)
        matched_old: set[str] = set()
        matched_new: set[str] = set()

        for key in set(old_symbols.keys()) & set(new_symbols.keys()):
            old_sym = old_symbols[key]
            new_sym = new_symbols[key]
            matched_old.add(key)
            matched_new.add(key)

            # Check for changes in the same symbol
            fact = self._compare_symbols(fc, old_sym, new_sym)
            if fact and self._intersects_hunks(fact, fc.hunks):
                facts.append(fact)

        # Then, try to match unmatched symbols by signature (for renames)
        unmatched_old = set(old_symbols.keys()) - matched_old
        unmatched_new = set(new_symbols.keys()) - matched_new

        for old_key in unmatched_old:
            old_sym = old_symbols[old_key]
            for new_key in unmatched_new:
                new_sym = new_symbols[new_key]
                if old_sym.signature_key() == new_sym.signature_key():
                    # This is a rename!
                    fact = self._make_fact(
                        fc=fc,
                        symbol=new_sym,
                        change_type=ChangeType.RENAMED,
                        old=old_sym.name,
                        new=new_sym.name,
                        line_old=old_sym.line,
                        line_new=new_sym.line,
                    )
                    if fact and self._intersects_hunks(fact, fc.hunks):
                        facts.append(fact)
                    matched_old.add(old_key)
                    matched_new.add(new_key)
                    break

        # Now process remaining unmatched symbols (added/removed)
        for key in unmatched_old:
            if key in matched_old:
                continue
            old_sym = old_symbols[key]
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

        for key in unmatched_new:
            if key in matched_new:
                continue
            new_sym = new_symbols[key]
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

        return facts

    def _compare_symbols(
        self,
        fc: FileChange,
        old_sym: PythonSymbol,
        new_sym: PythonSymbol,
    ) -> ChangeFact | None:
        """Compare two symbols and return a ChangeFact if there's a difference."""
        # Check for signature changes
        if old_sym.type_annotation != new_sym.type_annotation:
            return self._make_fact(
                fc=fc,
                symbol=new_sym,
                change_type=ChangeType.TYPE_CHANGED,
                old=old_sym.type_annotation,
                new=new_sym.type_annotation,
                line_old=old_sym.line,
                line_new=new_sym.line,
            )

        # Check for default value changes (for parameters, constants, fields)
        if old_sym.default_value != new_sym.default_value:
            return self._make_fact(
                fc=fc,
                symbol=new_sym,
                change_type=ChangeType.DEFAULT_CHANGED,
                old=old_sym.default_value,
                new=new_sym.default_value,
                line_old=old_sym.line,
                line_new=new_sym.line,
            )

        # Check for decorator changes
        if old_sym.decorators != new_sym.decorators:
            return self._make_fact(
                fc=fc,
                symbol=new_sym,
                change_type=ChangeType.SIGNATURE_CHANGED,
                old=", ".join(old_sym.decorators) if old_sym.decorators else None,
                new=", ".join(new_sym.decorators) if new_sym.decorators else None,
                line_old=old_sym.line,
                line_new=new_sym.line,
            )

        # Check for async change
        if old_sym.is_async != new_sym.is_async:
            return self._make_fact(
                fc=fc,
                symbol=new_sym,
                change_type=ChangeType.SIGNATURE_CHANGED,
                old="async" if old_sym.is_async else "sync",
                new="async" if new_sym.is_async else "sync",
                line_old=old_sym.line,
                line_new=new_sym.line,
            )

        return None

    def _symbol_value(self, sym: PythonSymbol) -> str:
        """Get a representative value for a symbol."""
        parts = []
        if sym.type_annotation:
            parts.append(f": {sym.type_annotation}")
        if sym.default_value:
            parts.append(f" = {sym.default_value}")
        return "".join(parts) if parts else sym.name

    def _make_fact(
        self,
        fc: FileChange,
        symbol: PythonSymbol,
        change_type: ChangeType,
        old: str | None,
        new: str | None,
        line_old: int | None,
        line_new: int | None,
    ) -> ChangeFact | None:
        """Create a ChangeFact from a PythonSymbol."""
        # Code snippet from the diff hunks around the line
        code_snippet = self._get_code_snippet(fc.hunks, line_old, line_new)

        location = CodeLocation(
            path=fc.path,
            line_old=line_old,
            line_new=line_new,
        )

        return ChangeFact(
            id="",  # Will be assigned later
            symbol=symbol.qualified_name,
            kind=symbol.kind,
            change_type=change_type,
            old=old,
            new=new,
            aliases=[symbol.name],
            location=location,
            code_snippet=code_snippet,
            help_text=symbol.docstring,
            extractor=self.name,
            public=not symbol.is_method or not symbol.name.startswith("_"),
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

        return "\n".join(lines[:20])  # Limit to 20 lines
