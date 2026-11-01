"""CLI flag extractor for argparse, click, and typer."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from driftcheck.extract.base import FileChange, Hunk
from driftcheck.models import ChangeFact, ChangeType, CodeLocation, SymbolKind


@dataclass
class CLIFlag:
    """Represents a CLI flag or command extracted from source code."""

    name: str  # Primary long flag (e.g., "--timeout") or subcommand path (e.g., "db migrate")
    short_flags: list[str]  # Short flags like ["-t", "-v"]
    default: str | None  # Source code of default value (from ast.unparse)
    type_annotation: str | None  # Type as source code
    choices: list[str] | None  # List of choice values as source code
    help_text: str | None  # Help text
    line: int  # Line number in source
    is_argument: bool  # True for positional arguments, False for options/flags
    is_subcommand: bool  # True for subcommands (click.group, typer commands)
    action: str | None  # argparse action (store_true, store_false, etc.)
    parent_command: str | None  # Parent command for nested subcommands

    def signature_key(self) -> tuple:
        """Return a key for matching flags across versions (help, type, position)."""
        return (
            self.help_text,
            self.type_annotation,
            self.choices,
            self.parent_command,
            self.is_argument,
            self.is_subcommand,
        )


class CLISymbolTable:
    """Symbol table for CLI flags in a single source file."""

    def __init__(self, source: str, file_path: str):
        self.source = source
        self.file_path = file_path
        self.tree = ast.parse(source)
        self.flags: dict[str, CLIFlag] = {}  # key -> CLIFlag
        self._extract_flags()

    def _extract_flags(self) -> None:
        """Walk the AST and extract all CLI flags."""
        for node in ast.walk(self.tree):
            # argparse: parser.add_argument(...)
            if isinstance(node, ast.Call):
                self._check_argparse_call(node)

            # Function definitions for click commands and typer commands
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_click_command(node)
                self._check_typer_command(node)

    def _get_line(self, node: ast.AST) -> int:
        """Get the line number of a node."""
        return getattr(node, "lineno", 1)

    def _unparse(self, node: ast.AST) -> str:
        """Safely unparse an AST node to source code."""
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def _check_argparse_call(self, node: ast.Call) -> None:
        """Check if this is an argparse add_argument call."""
        # Look for: parser.add_argument("--name", "-n", ...)
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and isinstance(node.func.value, ast.Name)
        ):
            return

        # Parse the arguments
        args = node.args
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}

        # First positional arg should be the flag name(s)
        if not args:
            return

        # Collect flag names from positional args
        flag_names = []
        short_flags = []

        for arg in args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                flag_name = arg.value
                flag_names.append(flag_name)
                if flag_name.startswith("-") and not flag_name.startswith("--"):
                    short_flags.append(flag_name)
                elif flag_name.startswith("--"):
                    short_flags.append(flag_name)

        if not flag_names:
            return

        # Primary name is the first long flag, or first short flag if no long flag
        # For positional arguments (no - prefix), use the name as-is
        primary_name = None
        for name in flag_names:
            if name.startswith("--"):
                primary_name = name
                break
        if primary_name is None:
            for name in flag_names:
                if name.startswith("-"):
                    primary_name = name
                    break
        if primary_name is None and flag_names:
            # Positional argument
            primary_name = flag_names[0]

        if primary_name is None:
            return

        # Extract other properties
        default = kwargs.get("default")
        type_ann = kwargs.get("type")
        choices = kwargs.get("choices")
        help_text = kwargs.get("help")
        action = kwargs.get("action")

        # Handle action="store_true"/"store_false" -> default is False/True
        default_source = self._unparse(default) if default else None
        if action and isinstance(action, ast.Constant):
            action_val = action.value
            if action_val == "store_true":
                default_source = "False"
            elif action_val == "store_false":
                default_source = "True"

        choices_source = None
        if choices and isinstance(choices, (ast.List, ast.Tuple)):
            choices_source = [self._unparse(el) for el in choices.elts]

        is_arg = not primary_name.startswith("-")

        flag = CLIFlag(
            name=primary_name,
            short_flags=short_flags,
            default=default_source,
            type_annotation=self._unparse(type_ann) if type_ann else None,
            choices=choices_source,
            help_text=self._unparse(help_text) if help_text else None,
            line=self._get_line(node),
            is_argument=is_arg,
            is_subcommand=False,
            action=self._unparse(action) if action else None,
            parent_command=None,
        )

        # Use primary name as key
        self.flags[primary_name] = flag

        # Also register aliases
        for short in short_flags:
            if short != primary_name:
                self.flags[short] = flag

        # Generate underscore/dash aliases for long flags
        if primary_name.startswith("--"):
            base = primary_name[2:]
            self.flags[base.replace("-", "_")] = flag
            self.flags[base.replace("_", "-")] = flag

    def _check_click_command(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Check for @click.command, @click.group, @group.command decorators."""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                self._process_click_decorator(decorator, node)
            elif isinstance(decorator, ast.Attribute):
                # @click.command (no args)
                if decorator.attr in ("command", "group"):
                    self._process_click_decorator(
                        ast.Call(func=decorator, args=[], keywords=[]), node
                    )

    def _process_click_decorator(
        self, call: ast.Call, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """Process a click command/group decorator."""
        # Check if it's click.command, click.group, or group.command
        is_click = False
        is_group = False

        if isinstance(call.func, ast.Attribute):
            if isinstance(call.func.value, ast.Name):
                if call.func.value.id == "click":
                    # Handle @click.command, @click.group, @click.option, @click.argument
                    if call.func.attr == "group":
                        is_click = True
                        is_group = True
                    elif call.func.attr == "command":
                        is_click = True
                    elif call.func.attr in ("option", "argument"):
                        # These are handled by _check_click_options, skip here
                        return
                # Check for group.command (e.g., cli.command)
                elif call.func.attr == "command":
                    # This is a subcommand on a group
                    is_click = True  # Treat as click command for processing

        if not is_click:
            return

        # Extract command name
        cmd_name: str | None = None
        if call.args:
            if isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
                cmd_name = call.args[0].value
        for kw in call.keywords:
            if (
                kw.arg == "name"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                cmd_name = kw.value.value

        if cmd_name is None:
            cmd_name = func_node.name.replace("_", "-")

        # Subcommand name is just the command name, not prefixed with group name
        full_name = cmd_name

        # For @click.group(), don't create a flag for the group function itself
        # (it's just a container for subcommands)
        if not is_group:
            flag = CLIFlag(
                name=full_name,
                short_flags=[],
                default=None,
                type_annotation=None,
                choices=None,
                help_text=ast.get_docstring(func_node),
                line=self._get_line(func_node),
                is_argument=False,
                is_subcommand=True,
                action=None,
                parent_command=None,
            )
            self.flags[full_name] = flag

        # Also check for @click.option decorators on this function
        # The parent command for options is the command name (full_name)
        self._check_click_options(func_node, full_name)

    def _check_click_options(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, parent_cmd: str | None
    ) -> None:
        """Check for @click.option and @click.argument decorators on a function."""
        for decorator in func_node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if (
                        isinstance(decorator.func.value, ast.Name)
                        and decorator.func.value.id == "click"
                    ):
                        if decorator.func.attr == "option":
                            self._process_click_option(decorator, parent_cmd)
                        elif decorator.func.attr == "argument":
                            self._process_click_argument(decorator, parent_cmd)

    def _process_click_option(self, call: ast.Call, parent_cmd: str | None) -> None:
        """Process a @click.option decorator."""
        args = call.args
        kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg}

        flag_names = []
        short_flags = []

        for arg in args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                flag_name = arg.value
                flag_names.append(flag_name)
                if flag_name.startswith("--"):
                    short_flags.append(flag_name)
                elif flag_name.startswith("-"):
                    short_flags.append(flag_name)

        if not flag_names:
            return

        primary_name = None
        for name in flag_names:
            if name.startswith("--"):
                primary_name = name
                break
        if primary_name is None and short_flags:
            primary_name = short_flags[0]

        if primary_name is None:
            return

        default = kwargs.get("default")
        type_ann = kwargs.get("type")
        help_text = kwargs.get("help")
        is_flag = kwargs.get("is_flag")

        default_source = self._unparse(default) if default else None
        if is_flag and isinstance(is_flag, ast.Constant) and is_flag.value is True:
            # is_flag=True means boolean flag, default is False
            default_source = "False"

        choices_source = None
        if type_ann and isinstance(type_ann, ast.Call):
            if isinstance(type_ann.func, ast.Attribute) and type_ann.func.attr == "Choice":
                if type_ann.args and isinstance(type_ann.args[0], (ast.List, ast.Tuple)):
                    choices_source = [self._unparse(el) for el in type_ann.args[0].elts]

        flag = CLIFlag(
            name=primary_name,
            short_flags=short_flags,
            default=default_source,
            type_annotation=self._unparse(type_ann) if type_ann else None,
            choices=choices_source,
            help_text=self._unparse(help_text) if help_text else None,
            line=self._get_line(call),
            is_argument=False,
            is_subcommand=False,
            action=None,
            parent_command=parent_cmd,
        )
        self.flags[primary_name] = flag

        for short in short_flags:
            if short != primary_name:
                self.flags[short] = flag

        if primary_name.startswith("--"):
            base = primary_name[2:]
            self.flags[base.replace("-", "_")] = flag
            self.flags[base.replace("_", "-")] = flag

    def _process_click_argument(self, call: ast.Call, parent_cmd: str | None) -> None:
        """Process a @click.argument decorator."""
        args = call.args

        arg_names = []
        for arg in args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                arg_names.append(arg.value)

        if not arg_names:
            return

        primary_name = arg_names[0]

        flag = CLIFlag(
            name=primary_name,
            short_flags=[],
            default=None,
            type_annotation=None,
            choices=None,
            help_text=None,
            line=self._get_line(call),
            is_argument=True,
            is_subcommand=False,
            action=None,
            parent_command=parent_cmd,
        )
        self.flags[primary_name] = flag

    def _check_typer_command(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Check for typer commands (function with typer.Option parameters)."""
        # Check if any parameter uses typer.Option or typer.Argument
        has_typer = False
        all_args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)

        # defaults are in node.args.defaults (for positional/keyword args)
        # and node.args.kw_defaults (for keyword-only args)
        defaults = list(node.args.defaults)
        kw_defaults = list(node.args.kw_defaults)

        # Map argument index to default node
        arg_defaults = {}
        num_args = len(all_args)
        num_defaults = len(defaults)
        for i in range(num_args - num_defaults, num_args):
            default_idx = i - (num_args - num_defaults)
            if default_idx < len(defaults):
                arg_defaults[i] = defaults[default_idx]

        for i, kw_default in enumerate(kw_defaults):
            if kw_default:
                # kwonlyargs index
                kw_arg_idx = len(node.args.posonlyargs) + len(node.args.args) + i
                arg_defaults[kw_arg_idx] = kw_default

        for i, _arg in enumerate(all_args):
            if i in arg_defaults and self._is_typer_option(arg_defaults[i]):
                has_typer = True
                break

        if not has_typer:
            return

        # This function is a typer command
        cmd_name = node.name.replace("_", "-")
        flag = CLIFlag(
            name=cmd_name,
            short_flags=[],
            default=None,
            type_annotation=None,
            choices=None,
            help_text=ast.get_docstring(node),
            line=self._get_line(node),
            is_argument=False,
            is_subcommand=True,
            action=None,
            parent_command=None,
        )
        self.flags[cmd_name] = flag

        # Process each parameter with typer.Option/Argument
        for i, arg in enumerate(all_args):
            if i in arg_defaults:
                default_node = arg_defaults[i]
                if isinstance(default_node, ast.Call):
                    self._process_typer_parameter(arg.arg, default_node, node)

    def _is_typer_option(self, node: ast.AST) -> bool:
        """Check if an expression is a typer.Option or typer.Argument call."""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "typer":
                    return node.func.attr in ("Option", "Argument")
        return False

    def _process_typer_parameter(
        self,
        param_name: str,
        default_node: ast.Call,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        """Process a typer.Option/Argument parameter."""
        kwargs = {kw.arg: kw.value for kw in default_node.keywords if kw.arg}
        args = default_node.args

        flag_names = []
        if args:
            for arg in args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    flag_names.append(arg.value)

        # Also check for --name in keywords
        for kw_name in ("name", "param_decls"):
            kw_value = kwargs.get(kw_name)
            if kw_value is not None and isinstance(kw_value, (ast.List, ast.Tuple)):
                for el in kw_value.elts:
                    if isinstance(el, ast.Constant) and isinstance(el.value, str):
                        flag_names.append(el.value)
            elif kw_value is not None and isinstance(kw_value, ast.Constant):
                if isinstance(kw_value.value, str):
                    flag_names.append(kw_value.value)

        if not flag_names:
            # Use parameter name as flag
            flag_names = [f"--{param_name.replace('_', '-')}"]

        # Primary name is first long flag
        primary_name = None
        short_flags = []
        for name in flag_names:
            if name.startswith("--"):
                primary_name = name
                break
            elif name.startswith("-"):
                short_flags.append(name)

        if primary_name is None:
            primary_name = flag_names[0]

        # For typer, the default value is the FIRST positional argument
        # typer.Option(default, *param_decls, **kwargs)
        default = args[0] if args else kwargs.get("default")
        help_text = kwargs.get("help")

        flag = CLIFlag(
            name=primary_name,
            short_flags=short_flags,
            default=self._unparse(default) if default else None,
            type_annotation=None,
            choices=None,
            help_text=self._unparse(help_text) if help_text else None,
            line=self._get_line(default_node),
            is_argument=not primary_name.startswith("-"),
            is_subcommand=False,
            action=None,
            parent_command=func_node.name.replace("_", "-"),
        )
        self.flags[primary_name] = flag

        for short in short_flags:
            if short != primary_name:
                self.flags[short] = flag

        if primary_name.startswith("--"):
            base = primary_name[2:]
            self.flags[base.replace("-", "_")] = flag
            self.flags[base.replace("_", "-")] = flag


class CLIExtractor:
    """Extract CLI flags from argparse, click, and typer code."""

    name = "py_cli"

    def applies_to(self, path: str) -> bool:
        return path.endswith(".py")

    def extract(
        self,
        fc: FileChange,
        old_src: str | None,
        new_src: str | None,
    ) -> list[ChangeFact]:
        """Extract CLI flag changes from a file change."""
        facts: list[ChangeFact] = []
        fact: ChangeFact | None = None

        # Build symbol tables for both versions
        old_table = CLISymbolTable(old_src, fc.old_path) if old_src else None
        new_table = CLISymbolTable(new_src, fc.new_path) if new_src else None

        # Get all unique flag keys (primary names only, not aliases)
        old_items = old_table.flags.items() if old_table else []
        new_items = new_table.flags.items() if new_table else []
        old_primary = {k: v for k, v in old_items if v.name == k}
        new_primary = {k: v for k, v in new_items if v.name == k}

        # First, try to match by signature (for renames)
        matched_old: set[str] = set()
        matched_new: set[str] = set()

        for old_key, old_flag in old_primary.items():
            for new_key, new_flag in new_primary.items():
                if old_flag.signature_key() == new_flag.signature_key() and old_key != new_key:
                    # This is a rename!
                    fact = self._make_fact(
                        fc=fc,
                        flag=new_flag,
                        change_type=ChangeType.RENAMED,
                        old=old_flag.name,
                        new=new_flag.name,
                        line_old=old_flag.line,
                        line_new=new_flag.line,
                    )
                    if fact and self._intersects_hunks(fact, fc.hunks):
                        facts.append(fact)
                    matched_old.add(old_key)
                    matched_new.add(new_key)
                    break

        # Now process unmatched flags
        for old_key, old_flag in old_primary.items():
            if old_key in matched_old:
                continue
            if old_key in new_primary:
                new_flag = new_primary[old_key]
                if new_key in matched_new:
                    continue
                # Same key, check for changes
                fact = self._compare_same_flag(fc, old_flag, new_flag)
                if fact and self._intersects_hunks(fact, fc.hunks):
                    facts.append(fact)
            else:
                # Removed
                fact = self._make_fact(
                    fc=fc,
                    flag=old_flag,
                    change_type=ChangeType.REMOVED,
                    old=old_flag.default,
                    new=None,
                    line_old=old_flag.line,
                    line_new=None,
                )
                if fact and self._intersects_hunks(fact, fc.hunks):
                    facts.append(fact)

        for new_key, new_flag in new_primary.items():
            if new_key in matched_new:
                continue
            if new_key not in old_primary:
                # Added
                fact = self._make_fact(
                    fc=fc,
                    flag=new_flag,
                    change_type=ChangeType.ADDED,
                    old=None,
                    new=new_flag.default,
                    line_old=None,
                    line_new=new_flag.line,
                )
                if fact and self._intersects_hunks(fact, fc.hunks):
                    facts.append(fact)

        return facts

    def _compare_same_flag(
        self,
        fc: FileChange,
        old_flag: CLIFlag,
        new_flag: CLIFlag,
    ) -> ChangeFact | None:
        """Compare two flags with the same key and return a ChangeFact if there's a difference."""

        # Check for default change
        if old_flag.default != new_flag.default:
            return self._make_fact(
                fc=fc,
                flag=new_flag,
                change_type=ChangeType.DEFAULT_CHANGED,
                old=old_flag.default,
                new=new_flag.default,
                line_old=old_flag.line,
                line_new=new_flag.line,
            )

        # Check for type change
        if old_flag.type_annotation != new_flag.type_annotation:
            return self._make_fact(
                fc=fc,
                flag=new_flag,
                change_type=ChangeType.TYPE_CHANGED,
                old=old_flag.type_annotation,
                new=new_flag.type_annotation,
                line_old=old_flag.line,
                line_new=new_flag.line,
            )

        # Check for choices change
        if old_flag.choices != new_flag.choices:
            old_choices = str(old_flag.choices) if old_flag.choices else None
            new_choices = str(new_flag.choices) if new_flag.choices else None
            return self._make_fact(
                fc=fc,
                flag=new_flag,
                change_type=ChangeType.CHOICES_CHANGED,
                old=old_choices,
                new=new_choices,
                line_old=old_flag.line,
                line_new=new_flag.line,
            )

        return None

    def _make_fact(
        self,
        fc: FileChange,
        flag: CLIFlag,
        change_type: ChangeType,
        old: str | None,
        new: str | None,
        line_old: int | None,
        line_new: int | None,
    ) -> ChangeFact:
        """Create a ChangeFact from a CLIFlag."""
        # Collect aliases
        aliases = []
        if flag.short_flags:
            aliases.extend(flag.short_flags)
        if flag.name.startswith("--"):
            base = flag.name[2:]
            aliases.append(base.replace("-", "_"))
            aliases.append(base.replace("_", "-"))

        # Code snippet from the diff hunks around the line
        code_snippet = self._get_code_snippet(fc.hunks, line_old, line_new)

        location = CodeLocation(
            path=fc.path,
            line_old=line_old,
            line_new=line_new,
        )

        return ChangeFact(
            id="",  # Will be assigned later
            symbol=flag.name,
            kind=SymbolKind.CLI_FLAG,
            change_type=change_type,
            old=old,
            new=new,
            aliases=aliases,
            location=location,
            code_snippet=code_snippet,
            help_text=flag.help_text,
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
            # Check if line falls within the hunk's range
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
                # Check if this line is near our target
                if new_no and abs(new_no - target_line) <= 3:
                    prefix = "+" if tag == "+" else ("-" if tag == "-" else " ")
                    lines.append(f"{prefix}{text.rstrip()}")
                elif old_no and abs(old_no - target_line) <= 3:
                    prefix = "+" if tag == "+" else ("-" if tag == "-" else " ")
                    lines.append(f"{prefix}{text.rstrip()}")

        return "\n".join(lines[:20])  # Limit to 20 lines
