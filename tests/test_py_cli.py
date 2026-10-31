"""Tests for CLI flag extractor (argparse, click, typer)."""

import pytest

from driftcheck.extract.base import FileChange, Hunk
from driftcheck.extract.py_cli import CLIExtractor, CLISymbolTable
from driftcheck.models import ChangeType, SymbolKind


class TestCLISymbolTable:
    """Tests for the CLISymbolTable class."""

    def test_argparse_simple_flag(self):
        """Test extracting a simple argparse flag."""
        source = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--timeout", "-t", type=int, default=30, help="Request timeout")
"""
        table = CLISymbolTable(source, "cli.py")
        assert "--timeout" in table.flags
        flag = table.flags["--timeout"]
        assert flag.name == "--timeout"
        assert "-t" in flag.short_flags
        assert flag.default == "30"
        assert flag.type_annotation == "int"
        # ast.unparse uses single quotes
        assert flag.help_text == "'Request timeout'"

    def test_argparse_store_true(self):
        """Test argparse action=store_true."""
        source = """
parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
"""
        table = CLISymbolTable(source, "cli.py")
        assert "--verbose" in table.flags
        flag = table.flags["--verbose"]
        assert flag.default == "False"
        assert flag.action == "'store_true'"

    def test_argparse_store_false(self):
        """Test argparse action=store_false."""
        source = """
parser.add_argument("--no-color", action="store_false", dest="color", help="Disable colors")
"""
        table = CLISymbolTable(source, "cli.py")
        assert "--no-color" in table.flags
        flag = table.flags["--no-color"]
        assert flag.default == "True"
        assert flag.action == "'store_false'"

    def test_argparse_choices(self):
        """Test argparse choices."""
        source = """
parser.add_argument("--mode", choices=["fast", "slow", "auto"], default="auto")
"""
        table = CLISymbolTable(source, "cli.py")
        assert "--mode" in table.flags
        flag = table.flags["--mode"]
        # ast.unparse uses single quotes for strings in lists
        assert flag.choices == ["'fast'", "'slow'", "'auto'"]
        assert flag.default == "'auto'"

    def test_argparse_positional_argument(self):
        """Test positional argument."""
        source = """
parser.add_argument("input_file", help="Input file path")
"""
        table = CLISymbolTable(source, "cli.py")
        # Positional args don't have -- prefix
        assert "input_file" in table.flags
        flag = table.flags["input_file"]
        assert flag.is_argument is True

    def test_click_option(self):
        """Test @click.option decorator."""
        source = """
import click

@click.command()
@click.option("--timeout", "-t", default=30, type=int, help="Request timeout")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def main(timeout, verbose):
    pass
"""
        table = CLISymbolTable(source, "cli.py")
        assert "--timeout" in table.flags
        flag = table.flags["--timeout"]
        assert flag.default == "30"
        assert flag.type_annotation == "int"
        assert flag.help_text == "'Request timeout'"

        assert "--verbose" in table.flags
        flag = table.flags["--verbose"]
        # click's is_flag=True doesn't have a default in the same way
        assert flag.default == "False"

    def test_click_command(self):
        """Test @click.command subcommand."""
        source = '''
import click

@click.group()
def cli():
    pass

@cli.command("serve")
@click.option("--port", "-p", default=8080, help="Port to listen on")
def serve(port):
    """Start the server."""
    pass
'''
        table = CLISymbolTable(source, "cli.py")
        # The group function "cli" should not create a flag
        # The subcommand "serve" should be created
        assert "serve" in table.flags
        flag = table.flags["serve"]
        assert flag.is_subcommand is True
        assert flag.help_text is not None and "Start the server" in flag.help_text

    def test_click_argument(self):
        """Test @click.argument."""
        source = """
import click

@click.command()
@click.argument("input_file")
def main(input_file):
    pass
"""
        table = CLISymbolTable(source, "cli.py")
        assert "input_file" in table.flags
        flag = table.flags["input_file"]
        assert flag.is_argument is True

    def test_typer_option(self):
        """Test typer.Option in function parameters."""
        source = '''
import typer

app = typer.Typer()

@app.command()
def serve(
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("localhost", "--host", help="Host to bind"),
):
    """Start the server."""
    pass
'''
        table = CLISymbolTable(source, "cli.py")
        assert "--port" in table.flags
        flag = table.flags["--port"]
        assert flag.default == "8080"
        assert flag.help_text == "'Port to listen on'"
        assert flag.parent_command == "serve"

        assert "--host" in table.flags
        flag = table.flags["--host"]
        assert flag.default == "'localhost'"

    def test_typer_argument(self):
        """Test typer.Argument in function parameters."""
        source = """
import typer

app = typer.Typer()

@app.command()
def copy(
    src: str = typer.Argument(help="Source file"),
    dst: str = typer.Argument(help="Destination file"),
):
    pass
"""
        table = CLISymbolTable(source, "cli.py")
        # Typer arguments become flags with -- prefix
        assert "--src" in table.flags or "src" in table.flags

    def test_typer_subcommand(self):
        """Test typer nested commands."""
        source = '''
import typer

app = typer.Typer()

@app.command()
def db_migrate(
    version: str = typer.Option("head", "--version", help="Migration version"),
):
    """Run database migrations."""
    pass
'''
        table = CLISymbolTable(source, "cli.py")
        assert "db-migrate" in table.flags
        flag = table.flags["db-migrate"]
        assert flag.is_subcommand is True


class TestCLIExtractor:
    """Tests for the CLIExtractor class."""

    def setup_method(self):
        self.extractor = CLIExtractor()

    def test_extract_default_changed(self):
        """Test detecting a default value change."""
        old_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--timeout", default=30, help="Timeout")
"""
        new_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--timeout", default=60, help="Timeout")
"""
        line_old = 'parser.add_argument("--timeout", default=30, help="Timeout")\n'
        line_new = 'parser.add_argument("--timeout", default=60, help="Timeout")\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=4,
                    old_len=1,
                    new_start=4,
                    new_len=1,
                    lines=[
                        ("-", 4, None, line_old),
                        ("+", None, 4, line_new),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        assert len(facts) == 1
        fact = facts[0]
        assert fact.symbol == "--timeout"
        assert fact.change_type == ChangeType.DEFAULT_CHANGED
        assert fact.old == "30"
        assert fact.new == "60"
        assert fact.kind == SymbolKind.CLI_FLAG

    def test_extract_added_flag(self):
        """Test detecting an added flag."""
        old_src = """
import argparse
parser = argparse.ArgumentParser()
"""
        new_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--verbose", "-v", action="store_true", help="Verbose")
"""
        line_add = 'parser.add_argument("--verbose", "-v", action="store_true", help="Verbose")\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=3,
                    old_len=0,
                    new_start=3,
                    new_len=2,
                    lines=[
                        ("+", None, 4, line_add),
                        ("+", None, 5, "\n"),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        assert len(facts) == 1
        fact = facts[0]
        assert fact.symbol == "--verbose"
        assert fact.change_type == ChangeType.ADDED
        assert fact.old is None
        assert fact.new == "False"  # store_true defaults to False
        assert "-v" in fact.aliases

    def test_extract_removed_flag(self):
        """Test detecting a removed flag."""
        old_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--debug", help="Debug mode")
"""
        new_src = """
import argparse
parser = argparse.ArgumentParser()
"""
        line_rem = 'parser.add_argument("--debug", help="Debug mode")\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=4,
                    old_len=1,
                    new_start=3,
                    new_len=0,
                    lines=[
                        ("-", 4, None, line_rem),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        assert len(facts) == 1
        fact = facts[0]
        assert fact.symbol == "--debug"
        assert fact.change_type == ChangeType.REMOVED
        assert fact.old is None  # No default
        assert fact.new is None

    def test_extract_renamed_flag(self):
        """Test detecting a renamed flag."""
        old_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--timeout", default=30, help="Request timeout")
"""
        new_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--request-timeout", default=30, help="Request timeout")
"""
        line_old = 'parser.add_argument("--timeout", default=30, help="Request timeout")\n'
        line_new = 'parser.add_argument("--request-timeout", default=30, help="Request timeout")\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=4,
                    old_len=1,
                    new_start=4,
                    new_len=1,
                    lines=[
                        ("-", 4, None, line_old),
                        ("+", None, 4, line_new),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        # Should detect RENAMED
        renamed_facts = [f for f in facts if f.change_type == ChangeType.RENAMED]
        assert len(renamed_facts) == 1
        fact = renamed_facts[0]
        assert fact.old == "--timeout"
        assert fact.new == "--request-timeout"

    def test_extract_type_changed(self):
        """Test detecting a type change."""
        old_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--count", type=int, default=10)
"""
        new_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--count", type=float, default=10)
"""
        line_old = 'parser.add_argument("--count", type=int, default=10)\n'
        line_new = 'parser.add_argument("--count", type=float, default=10)\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=4,
                    old_len=1,
                    new_start=4,
                    new_len=1,
                    lines=[
                        ("-", 4, None, line_old),
                        ("+", None, 4, line_new),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        type_facts = [f for f in facts if f.change_type == ChangeType.TYPE_CHANGED]
        assert len(type_facts) == 1
        fact = type_facts[0]
        assert fact.old == "int"
        assert fact.new == "float"

    def test_extract_choices_changed(self):
        """Test detecting a choices change."""
        old_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["fast", "slow"], default="fast")
"""
        new_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["fast", "slow", "auto"], default="fast")
"""
        line_old = 'parser.add_argument("--mode", choices=["fast", "slow"], default="fast")\n'
        line_new = (
            'parser.add_argument("--mode", choices=["fast", "slow", "auto"], default="fast")\n'
        )
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=4,
                    old_len=1,
                    new_start=4,
                    new_len=1,
                    lines=[
                        ("-", 4, None, line_old),
                        ("+", None, 4, line_new),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        choice_facts = [f for f in facts if f.change_type == ChangeType.CHOICES_CHANGED]
        assert len(choice_facts) == 1

    def test_click_option_default_changed(self):
        """Test click option default change."""
        old_src = """
import click

@click.command()
@click.option("--port", default=8080, help="Port")
def main(port):
    pass
"""
        new_src = """
import click

@click.command()
@click.option("--port", default=3000, help="Port")
def main(port):
    pass
"""
        line_old = '    @click.option("--port", default=8080, help="Port")\n'
        line_new = '    @click.option("--port", default=3000, help="Port")\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=5,
                    old_len=1,
                    new_start=5,
                    new_len=1,
                    lines=[
                        ("-", 5, None, line_old),
                        ("+", None, 5, line_new),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        default_facts = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(default_facts) == 1
        fact = default_facts[0]
        assert fact.old == "8080"
        assert fact.new == "3000"

    def test_typer_option_default_changed(self):
        """Test typer option default change."""
        old_src = """
import typer

app = typer.Typer()

@app.command()
def serve(port: int = typer.Option(8080, "--port", help="Port")):
    pass
"""
        new_src = """
import typer

app = typer.Typer()

@app.command()
def serve(port: int = typer.Option(3000, "--port", help="Port")):
    pass
"""
        line_old = 'def serve(port: int = typer.Option(8080, "--port", help="Port")):\n'
        line_new = 'def serve(port: int = typer.Option(3000, "--port", help="Port")):\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=7,
                    old_len=1,
                    new_start=7,
                    new_len=1,
                    lines=[
                        ("-", 7, None, line_old),
                        ("+", None, 7, line_new),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        default_facts = [f for f in facts if f.change_type == ChangeType.DEFAULT_CHANGED]
        assert len(default_facts) == 1
        fact = default_facts[0]
        assert fact.old == "8080"
        assert fact.new == "3000"

    def test_ignores_flags_outside_hunks(self):
        """Test that flags outside diff hunks are ignored."""
        old_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--timeout", default=30)
parser.add_argument("--debug", default=False)
"""
        new_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--timeout", default=60)
parser.add_argument("--debug", default=False)
"""
        # Only the --timeout line is in the hunk (line 4)
        line_old = 'parser.add_argument("--timeout", default=30)\n'
        line_new = 'parser.add_argument("--timeout", default=60)\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=4,
                    old_len=1,
                    new_start=4,
                    new_len=1,
                    lines=[
                        ("-", 4, None, line_old),
                        ("+", None, 4, line_new),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        # Only --timeout should be detected, not --debug
        assert len(facts) == 1
        assert facts[0].symbol == "--timeout"

    def test_aliases_generated(self):
        """Test that aliases are generated for flags."""
        old_src = ""
        new_src = """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", "-n", default=False, help="Dry run")
"""
        line_add = 'parser.add_argument("--dry-run", "-n", default=False, help="Dry run")\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="added",
            hunks=[
                Hunk(
                    old_start=0,
                    old_len=0,
                    new_start=1,
                    new_len=5,
                    lines=[
                        ("+", None, 1, "import argparse\n"),
                        ("+", None, 2, "parser = argparse.ArgumentParser()\n"),
                        ("+", None, 3, line_add),
                        ("+", None, 4, "\n"),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        assert len(facts) == 1
        fact = facts[0]
        assert fact.symbol == "--dry-run"
        assert "-n" in fact.aliases
        assert "dry_run" in fact.aliases
        assert "dry-run" in fact.aliases

    def test_code_snippet_included(self):
        """Test that code snippet is included in facts."""
        old_src = """
parser.add_argument("--timeout", default=30, help="Timeout")
"""
        new_src = """
parser.add_argument("--timeout", default=60, help="Timeout")
"""
        line_old = 'parser.add_argument("--timeout", default=30, help="Timeout")\n'
        line_new = 'parser.add_argument("--timeout", default=60, help="Timeout")\n'
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=2,
                    old_len=1,
                    new_start=2,
                    new_len=1,
                    lines=[
                        ("-", 2, None, line_old),
                        ("+", None, 2, line_new),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        assert len(facts) == 1
        fact = facts[0]
        assert fact.code_snippet != ""
        assert "--timeout" in fact.code_snippet

    def test_help_text_extracted(self):
        """Test that help text is extracted."""
        old_src = """
parser.add_argument("--timeout", default=30, help="Request timeout in seconds")
"""
        new_src = """
parser.add_argument("--timeout", default=60, help="Request timeout in seconds")
"""
        line_old = (
            'parser.add_argument("--timeout", default=30, help="Request timeout in seconds")\n'
        )
        line_new = (
            'parser.add_argument("--timeout", default=60, help="Request timeout in seconds")\n'
        )
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=2,
                    old_len=1,
                    new_start=2,
                    new_len=1,
                    lines=[
                        ("-", 2, None, line_old),
                        ("+", None, 2, line_new),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        assert len(facts) == 1
        fact = facts[0]
        assert fact.help_text == "'Request timeout in seconds'"

    def test_subcommand_extracted(self):
        """Test that subcommands are extracted."""
        old_src = '''
import click

@click.group()
def cli():
    pass

@cli.command("serve")
def serve():
    """Start server."""
    pass
'''
        new_src = '''
import click

@click.group()
def cli():
    pass

@cli.command("serve")
def serve():
    """Start server."""
    pass

@cli.command("stop")
def stop():
    """Stop server."""
    pass
'''
        fc = FileChange(
            old_path="cli.py",
            new_path="cli.py",
            status="modified",
            hunks=[
                Hunk(
                    old_start=11,
                    old_len=0,
                    new_start=11,
                    new_len=6,
                    lines=[
                        ("+", None, 11, "\n"),
                        ("+", None, 12, '@cli.command("stop")\n'),
                        ("+", None, 13, "def stop():\n"),
                        ("+", None, 14, '    """Stop server."""\n'),
                        ("+", None, 15, "    pass\n"),
                    ],
                )
            ],
        )
        facts = self.extractor.extract(fc, old_src, new_src)

        # Should detect the new subcommand
        added_facts = [f for f in facts if f.change_type == ChangeType.ADDED]
        subcommand_facts = [
            f for f in added_facts if f.kind == SymbolKind.CLI_FLAG and f.symbol == "stop"
        ]
        assert len(subcommand_facts) == 1
        fact = subcommand_facts[0]
        # Subcommand facts have the command name as symbol
        assert fact.symbol == "stop"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
