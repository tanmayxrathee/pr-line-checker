"""Tests for driftcheck extract diff parsing."""

from driftcheck.extract.base import FileChange
from driftcheck.extract.diffparse import parse_diff


class TestParseDiff:
    """Tests for parse_diff function."""

    def test_empty_diff(self):
        """Test parsing empty diff returns empty list."""
        result = parse_diff("")
        assert result == []

    def test_added_file(self):
        """Test parsing an added file diff."""
        diff_text = """diff --git a/new_file.py b/new_file.py
new file mode 100644
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,4 @@
+def hello():
+    print("start")
+    return "world"
+
"""
        result = parse_diff(diff_text)
        assert len(result) == 1
        fc = result[0]
        assert fc.status == "added"
        assert fc.old_path == "/dev/null"
        assert fc.new_path == "new_file.py"
        assert len(fc.hunks) == 1
        hunk = fc.hunks[0]
        assert hunk.old_start == 0
        assert hunk.old_len == 0
        assert hunk.new_start == 1
        assert hunk.new_len == 4
        assert len(hunk.lines) == 4
        assert hunk.lines[0] == ("+", None, 1, "def hello():")
        assert hunk.lines[1] == ("+", None, 2, '    print("start")')
        assert hunk.lines[2] == ("+", None, 3, '    return "world"')
        assert hunk.lines[3] == ("+", None, 4, "")

    def test_removed_file(self):
        """Test parsing a removed file diff."""
        diff_text = """diff --git a/old_file.py b/old_file.py
deleted file mode 100644
--- a/old_file.py
+++ /dev/null
@@ -1,4 +0,0 @@
-def hello():
-    print("start")
-    return "world"
-
"""
        result = parse_diff(diff_text)
        assert len(result) == 1
        fc = result[0]
        assert fc.status == "removed"
        assert fc.old_path == "old_file.py"
        assert fc.new_path == "/dev/null"
        assert len(fc.hunks) == 1
        hunk = fc.hunks[0]
        assert hunk.old_start == 1
        assert hunk.old_len == 4
        assert hunk.new_start == 0
        assert hunk.new_len == 0
        assert len(hunk.lines) == 4
        assert hunk.lines[0] == ("-", 1, None, "def hello():")
        assert hunk.lines[1] == ("-", 2, None, '    print("start")')
        assert hunk.lines[2] == ("-", 3, None, '    return "world"')
        assert hunk.lines[3] == ("-", 4, None, "")

    def test_modified_file(self):
        """Test parsing a modified file diff."""
        diff_text = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1,4 +1,5 @@
 def hello():
     print("start")
-    return "world"
+    return "universe"
+    # comment
     print("end")
"""
        result = parse_diff(diff_text)
        assert len(result) == 1
        fc = result[0]
        assert fc.status == "modified"
        assert fc.old_path == "file.py"
        assert fc.new_path == "file.py"
        assert len(fc.hunks) == 1
        hunk = fc.hunks[0]
        assert hunk.old_start == 1
        assert hunk.old_len == 4
        assert hunk.new_start == 1
        assert hunk.new_len == 5
        # unidiff doesn't include trailing empty context lines, so 6 lines not 7
        assert len(hunk.lines) == 6
        assert hunk.lines[0] == (" ", 1, 1, "def hello():")
        assert hunk.lines[1] == (" ", 2, 2, '    print("start")')
        assert hunk.lines[2] == ("-", 3, None, '    return "world"')
        assert hunk.lines[3] == ("+", None, 3, '    return "universe"')
        assert hunk.lines[4] == ("+", None, 4, "    # comment")
        assert hunk.lines[5] == (" ", 4, 5, '    print("end")')

    def test_renamed_file(self):
        """Test parsing a renamed file diff."""
        diff_text = """diff --git a/old_name.py b/new_name.py
similarity index 100%
rename from old_name.py
rename to new_name.py
--- a/old_name.py
+++ b/new_name.py
@@ -1,3 +1,3 @@
-def hello():
+def hello_world():
     print("test")
     return "world"
"""
        result = parse_diff(diff_text)
        assert len(result) == 1
        fc = result[0]
        assert fc.status == "renamed"
        assert fc.old_path == "old_name.py"
        assert fc.new_path == "new_name.py"

    def test_multiple_files(self):
        """Test parsing a diff with multiple files - separate patches."""
        diff_text1 = """diff --git a/file1.py b/file1.py
--- a/file1.py
+++ b/file1.py
@@ -1,1 +1,1 @@
-def foo()
+def foo()
"""
        diff_text2 = """diff --git a/file2.py b/file2.py
--- a/file2.py
+++ b/file2.py
@@ -1,1 +1,1 @@
-def bar()
+def bar()
"""
        result1 = parse_diff(diff_text1)
        result2 = parse_diff(diff_text2)
        assert len(result1) == 1
        assert result1[0].path == "file1.py"
        assert len(result2) == 1
        assert result2[0].path == "file2.py"

    def test_multiple_hunks(self):
        """Test parsing a file with multiple hunks."""
        diff_text = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def func1():
-    return 1
+    return 2
     pass
@@ -4,3 +4,3 @@
 def func2():
-    return 3
+    return 4
     pass
"""
        result = parse_diff(diff_text)
        assert len(result) == 1
        fc = result[0]
        assert len(fc.hunks) == 2
        assert fc.hunks[0].old_start == 1
        assert fc.hunks[1].old_start == 4

    def test_line_numbers(self):
        """Test that line numbers are correctly parsed."""
        diff_text = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -5,4 +5,4 @@
 def example():
     x = 1
-    y = 2
+    y = 3
     z = 4
"""
        result = parse_diff(diff_text)
        assert len(result) == 1
        fc = result[0]
        hunk = fc.hunks[0]
        assert hunk.lines[0] == (" ", 5, 5, "def example():")
        assert hunk.lines[1] == (" ", 6, 6, "    x = 1")
        assert hunk.lines[2] == ("-", 7, None, "    y = 2")
        assert hunk.lines[3] == ("+", None, 7, "    y = 3")
        assert hunk.lines[4] == (" ", 8, 8, "    z = 4")


class TestFileChange:
    """Tests for FileChange dataclass."""

    def test_path_property_added(self):
        """Test path property for added file."""
        fc = FileChange(
            old_path="/dev/null",
            new_path="new_file.py",
            status="added",
            hunks=[],
        )
        assert fc.path == "new_file.py"

    def test_path_property_removed(self):
        """Test path property for removed file."""
        fc = FileChange(
            old_path="old_file.py",
            new_path="/dev/null",
            status="removed",
            hunks=[],
        )
        assert fc.path == "old_file.py"

    def test_path_property_modified(self):
        """Test path property for modified file."""
        fc = FileChange(
            old_path="file.py",
            new_path="file.py",
            status="modified",
            hunks=[],
        )
        assert fc.path == "file.py"
