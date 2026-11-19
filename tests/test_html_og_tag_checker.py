"""Tests for html_og_tag_checker.

Run from the repo root:

    python3 tests/test_html_og_tag_checker.py
"""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "html_og_tag_checker.py"

sys.path.insert(0, str(REPO / "src"))
import html_og_tag_checker as tool  # noqa: E402


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)
    return str(path)


def run_cli(args, input=None, cwd=None):
    result = subprocess.run(
        [sys.executable, str(SRC)] + args,
        cwd=cwd or str(REPO), capture_output=True, text=True,
        input=input)
    return result.returncode, result.stdout, result.stderr


CLEAN = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Page</title>
<meta property="og:title" content="Page">
<meta property="og:description" content="A page.">
<meta property="og:image" content="https://example.com/card.png">
</head>
<body>
<p>Hello.</p>
</body>
</html>
"""

FLAGGED = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Page</title>
<meta property="og:title" content="Page">
</head>
<body>
<p>Hello.</p>
</body>
</html>
"""


class TestCheckText(unittest.TestCase):
    def test_all_three_present_passes(self):
        bad, error = tool.check_text(CLEAN)
        self.assertEqual((bad, error), ([], None))

    def test_missing_two_tags_reported_on_head_line(self):
        bad, error = tool.check_text(FLAGGED)
        self.assertIsNone(error)
        self.assertEqual(len(bad), 2)
        self.assertEqual(bad[0]["line"], 3)
        self.assertIn('"og:description"', bad[0]["reason"])
        self.assertEqual(bad[1]["line"], 3)
        self.assertIn('"og:image"', bad[1]["reason"])

    def test_missing_all_three_in_required_order(self):
        bad, error = tool.check_text(
            "<html><head><title>t</title></head></html>\n")
        self.assertEqual([f["reason"] for f in bad],
                         ['og tag "og:title" is missing',
                          'og tag "og:description" is missing',
                          'og tag "og:image" is missing'])
        self.assertTrue(all(f["line"] == 1 for f in bad))

    def test_no_head_tag_reports_line_one(self):
        bad, error = tool.check_text("<html><body><p>x</p></body></html>\n")
        self.assertEqual(len(bad), 3)
        self.assertTrue(all(f["line"] == 1 for f in bad))

    def test_uppercase_property_counts_as_present(self):
        bad, error = tool.check_text(
            '<html><head>'
            '<meta property="OG:TITLE" content="T">'
            '<meta property="OG:DESCRIPTION" content="D">'
            '<meta property="OG:IMAGE" content="I">'
            '</head></html>\n')
        self.assertEqual((bad, error), ([], None))

    def test_tag_inside_comment_does_not_count(self):
        bad, error = tool.check_text(
            '<html><head>'
            '<!-- <meta property="og:description" content="D"> -->'
            '<meta property="og:title" content="T">'
            '<meta property="og:image" content="I">'
            '</head></html>\n')
        self.assertEqual(len(bad), 1)
        self.assertIn('"og:description"', bad[0]["reason"])

    def test_meta_name_description_does_not_count(self):
        bad, error = tool.check_text(
            '<html><head>'
            '<meta name="description" content="A page.">'
            '<meta property="og:title" content="T">'
            '<meta property="og:image" content="I">'
            '</head></html>\n')
        self.assertEqual(len(bad), 1)
        self.assertIn('"og:description"', bad[0]["reason"])

    def test_empty_content_counts_as_present(self):
        bad, error = tool.check_text(
            '<html><head>'
            '<meta property="og:title" content="T">'
            '<meta property="og:description" content="">'
            '<meta property="og:image" content="I">'
            '</head></html>\n')
        self.assertEqual((bad, error), ([], None))

    def test_tag_in_body_counts_as_present(self):
        bad, error = tool.check_text(
            '<html><head><title>t</title></head><body>'
            '<meta property="og:title" content="T">'
            '<meta property="og:description" content="D">'
            '<meta property="og:image" content="I">'
            '</body></html>\n')
        self.assertEqual((bad, error), ([], None))

    def test_duplicate_tags_pass(self):
        bad, error = tool.check_text(
            '<html><head>'
            '<meta property="og:title" content="T">'
            '<meta property="og:title" content="T2">'
            '<meta property="og:description" content="D">'
            '<meta property="og:image" content="I">'
            '</head></html>\n')
        self.assertEqual((bad, error), ([], None))

    def test_self_closing_tags_count(self):
        bad, error = tool.check_text(
            '<html><head>'
            '<meta property="og:title" content="T" />'
            '<meta property="og:description" content="D" />'
            '<meta property="og:image" content="I" />'
            '</head></html>\n')
        self.assertEqual((bad, error), ([], None))

    def test_other_og_tags_do_not_cover_required_ones(self):
        bad, error = tool.check_text(
            '<html><head>'
            '<meta property="og:type" content="website">'
            '<meta property="og:url" content="https://example.com/">'
            '</head></html>\n')
        self.assertEqual(len(bad), 3)

    def test_empty_document_reports_all_three(self):
        bad, error = tool.check_text("")
        self.assertEqual(len(bad), 3)
        self.assertTrue(all(f["line"] == 1 for f in bad))


class TestCli(unittest.TestCase):
    def test_clean_file_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", CLEAN)
            code, out, err = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn("every Open Graph tag is present", out)

    def test_flagged_file_exits_one_with_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", FLAGGED)
            code, out, err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn('line 3 og tag "og:description" is missing', out)
            self.assertIn("Checked 1 file(s), 2 og tag(s)", out)

    def test_folder_walks_html_and_htm_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.html", CLEAN)
            write(tmp, "b.htm", FLAGGED)
            write(tmp, "c.txt", FLAGGED)
            code, out, err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s), 2 og tag(s)", out)

    def test_no_recursive_stops_at_top_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.html", CLEAN)
            write(tmp, "sub/b.html", FLAGGED)
            code, out, err = run_cli(["--no-recursive", tmp])
            self.assertEqual(code, 0)
            code, out, err = run_cli([tmp])
            self.assertEqual(code, 1)

    def test_exclude_skips_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.html", CLEAN)
            write(tmp, "b.html", FLAGGED)
            code, out, err = run_cli(["--exclude", "b.html", tmp])
            self.assertEqual(code, 0)

    def test_git_folder_never_walked(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.html", CLEAN)
            write(tmp, ".git/b.html", FLAGGED)
            code, out, err = run_cli([tmp])
            self.assertEqual(code, 0)

    def test_file_given_directly_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "page.txt", FLAGGED)
            code, out, err = run_cli([path])
            self.assertEqual(code, 1)

    def test_missing_path_is_usage_error(self):
        code, out, err = run_cli(["no-such-file.html"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_no_paths_is_usage_error(self):
        code, out, err = run_cli([])
        self.assertEqual(code, 2)

    def test_invalid_utf8_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.html"
            path.write_bytes(b'<html><head>\xff</head></html>\n')
            code, out, err = run_cli([str(path)])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", FLAGGED)
            code, out, err = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["findings"], 2)
            self.assertEqual(data["files"][0]["findings"][0]["line"], 3)

    def test_stdin_clean(self):
        code, out, err = run_cli(["--stdin"], input=CLEAN)
        self.assertEqual(code, 0)
        self.assertIn("every Open Graph tag is present", out)

    def test_stdin_flagged(self):
        code, out, err = run_cli(["--stdin"], input=FLAGGED)
        self.assertEqual(code, 1)
        self.assertIn('FAIL <stdin>: line 3 og tag "og:description"'
                      ' is missing', out)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", FLAGGED)
            before = Path(path).read_text()
            run_cli([path])
            self.assertEqual(Path(path).read_text(), before)

    def test_cli_runs_from_another_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.html", CLEAN)
            result = subprocess.run(
                [sys.executable, str(SRC), "a.html"],
                cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn("every Open Graph tag is present",
                          result.stdout)

    def test_cli_runs_under_fake_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", CLEAN)
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                code, out, err = run_cli([path])
            finally:
                if old_home is None:
                    del os.environ["HOME"]
                else:
                    os.environ["HOME"] = old_home
            self.assertEqual(code, 0)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        clean = subprocess.run(
            [sys.executable, "src/html_og_tag_checker.py",
             "examples/clean.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0)
        self.assertIn(clean.stdout.strip(), readme)
        flagged = subprocess.run(
            [sys.executable, "src/html_og_tag_checker.py",
             "examples/flagged.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(flagged.returncode, 1)
        self.assertIn(flagged.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/html_og_tag_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 3 file(s), 2 og tag(s) missing "
                      "in 1 file(s).", folder.stdout)
        self.assertIn("Checked 3 file(s), 2 og tag(s) missing "
                      "in 1 file(s).", readme)
        edge = subprocess.run(
            [sys.executable, "src/html_og_tag_checker.py",
             "examples/edge.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(edge.returncode, 0)
        self.assertIn(edge.stdout.strip(), readme)
        js = subprocess.run(
            [sys.executable, "src/html_og_tag_checker.py",
             "--json", "examples/flagged.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)
        stdin = subprocess.run(
            [sys.executable, "src/html_og_tag_checker.py",
             "--stdin"],
            input="<html><head><title>t</title></head>"
                  "<body>x</body></html>\n",
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(stdin.returncode, 1)
        self.assertIn(stdin.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True, skip_examples=True):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")
                       and not (skip_tests and d == "tests")
                       and not (skip_examples and d == "examples")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_real_secrets_outside_tests_and_examples(self):
        # The source holds no key values at all; the tests
        # and examples hold fake values only, so they are
        # excluded from this scan.
        patterns = [
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
            re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
            re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
            re.compile(r"AIza[0-9A-Za-z_-]{35}"),
            re.compile(r"[rs]k_(?:live|test)_[A-Za-z0-9]{16,}"),
            re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
            re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ"),
        ]
        hits = []
        for path in self._repo_files():
            text = path.read_text(errors="ignore")
            for pattern in patterns:
                if pattern.search(text):
                    hits.append("%s: %s" % (path.name, pattern.pattern))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src/html_og_tag_checker.py",
                       REPO / "tests/test_html_og_tag_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"html_og_tag_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src/html_og_tag_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_html_og_tag_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        self.assertIn("html-meta-description-checker-cli", readme)
        self.assertIn("html-title-checker-cli", readme)


if __name__ == "__main__":
    unittest.main()
