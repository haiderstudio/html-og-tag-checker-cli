#!/usr/bin/env python3
"""Check HTML files carry Open Graph tags.

Run: python3 src/html_og_tag_checker.py page.html
     python3 src/html_og_tag_checker.py site/
     python3 src/html_og_tag_checker.py --stdin < page.html

A page shared without Open Graph tags shows as a
bare link with no title, no description and no
image — the share looks broken and nobody clicks
it, and the author only finds out when someone
else shares the page. This tool reads each HTML
file, checks it carries og:title, og:description
and og:image (<meta property="og:*">), and reports
each missing tag with the file and the line,
exiting 1, so it can fail a CI run. A file with
all three tags exits 0.

A missing tag is reported on the line of the
opening <head> tag when the file has one, because
that is where the fix goes: the tags belong inside
<head>. A file with no <head> tag reports its
missing tags on line 1.

Only presence is checked. A tag counts as present
whatever its content holds — even an empty
content value — and the tool never checks what a
tag points at: it never fetches an og:image URL
and never checks that a title or description
reads well. That is a different job.

A file given directly on the command line is always
checked, whatever its name. A folder is walked for
files ending in .html or .htm only, recursively by
default (--no-recursive stops at the top level).
.git folders are never walked, and directory links
are never followed.

It never rewrites a file, never touches the network,
and reads only the files and folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

__version__ = "1.0.0"

HTML_SUFFIXES = (".html", ".htm")

REQUIRED_TAGS = ("og:title", "og:description", "og:image")


class _OgTagParser(HTMLParser):
    """Collect the og:* meta tags in one HTML document.

    Tags inside HTML comments are never seen: the
    parser reports comments separately, so a tag
    that only exists inside a comment does not
    count as present.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = set()
        self.head_line = None

    def handle_starttag(self, tag, attrs):
        if tag == "head" and self.head_line is None:
            self.head_line = self.getpos()[0]
        if tag == "meta":
            props = {name.lower(): value
                     for name, value in attrs if name}
            prop = props.get("property", "")
            if prop:
                self.found.add(prop.strip().lower())

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def check_text(text):
    """Check one document's text.

    Returns (findings, error): findings is a list of
    {"line": int, "reason": str} in the order the
    tags are required, and error is None — plain
    HTML text has no parse failure to report.
    """
    parser = _OgTagParser()
    parser.feed(text)
    parser.close()
    line = parser.head_line or 1
    findings = []
    for tag in REQUIRED_TAGS:
        if tag not in parser.found:
            findings.append({
                "line": line,
                "reason": 'og tag "%s" is missing' % tag,
            })
    return findings, None


def check_file(path):
    """Check one file. Returns (findings, error)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], str(exc)
    return check_text(text)


def _is_html_file(path):
    return Path(path).name.lower().endswith(HTML_SUFFIXES)


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of HTML files.

    A file given directly is always checked, whatever its
    name. A folder is walked for files ending in .html
    or .htm only. .git folders are never walked, and
    directory links are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(dirpath) / name
                    if not _is_html_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_finding(path, finding):
    """One human-readable line for one missing tag."""
    return ("FAIL %s: line %d %s"
            % (path, finding["line"], finding["reason"]))


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no HTML files found", file=sys.stderr)
        return 2
    results = []
    findings = 0
    files_with_findings = 0
    for path in files:
        bad, error = check_file(path)
        count = len(bad) + (1 if error else 0)
        if count:
            findings += count
            files_with_findings += 1
        results.append({"path": path, "findings": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "findings": findings},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for finding in result["findings"]:
                print(format_finding(result["path"], finding))
        if findings:
            print("Checked %d file(s), %d og tag(s) missing "
                  "in %d file(s)."
                  % (len(files), findings, files_with_findings))
        else:
            print("OK — %d file(s) checked, every Open Graph "
                  "tag is present." % len(files))
    return 1 if findings else 0


def run_stdin(as_json=False):
    """Check one HTML document read from standard input."""
    try:
        text = sys.stdin.buffer.read().decode("utf-8")
    except UnicodeDecodeError:
        print("FAIL <stdin>: not valid UTF-8")
        return 1
    bad, error = check_text(text)
    findings = len(bad) + (1 if error else 0)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "findings": bad,
                        "error": error}],
             "checked": 1, "findings": findings},
            indent=2))
    else:
        if error:
            print("FAIL <stdin>: %s" % error)
        for finding in bad:
            print(format_finding("<stdin>", finding))
        if findings:
            print("Checked 1 file(s), %d og tag(s) missing "
                  "in 1 file(s)." % findings)
        else:
            print("OK — 1 file(s) checked, every Open Graph "
                  "tag is present.")
    return 1 if findings else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="html_og_tag_checker",
        description="Check HTML files carry og:title, "
                    "og:description and og:image, fail CI "
                    "when one is missing.")
    parser.add_argument("paths", nargs="*",
                        help="HTML files or folders to walk")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one HTML document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one HTML file or folder")
    return run(args.paths,
               recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
