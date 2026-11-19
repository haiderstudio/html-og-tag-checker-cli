# html-og-tag-checker-cli

Check HTML files carry Open Graph tags — fail CI when one is missing.

[![CI](https://github.com/haiderstudio/html-og-tag-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/html-og-tag-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`html_og_tag_checker` reads each HTML file,
checks it carries `og:title`, `og:description`
and `og:image` (`<meta property="og:*">`), and
reports each missing tag with the file and the
line. It exits 1 when any tag is missing, so it
can fail a CI run. A file with all three tags
exits 0.

- A missing tag is reported on the line of the
  opening `<head>` tag when the file has one,
  because that is where the fix goes: the tags
  belong inside `<head>`. A file with no `<head>`
  tag reports its missing tags on line 1.
- Only presence is checked. A tag counts as
  present whatever its content holds — even an
  empty content value — and the tool never checks
  what a tag points at: it never fetches an
  `og:image` URL and never checks that a title or
  description reads well.
- Tag names are matched without caring about
  capital letters, so `OG:TITLE` counts the same
  as `og:title`. A tag that only exists inside an
  HTML comment does not count — it is not a real
  tag on the page.
- A file given directly on the command line is
  always checked, whatever its name. A folder is
  walked for files ending in `.html` or `.htm`
  only, recursively by default (`--no-recursive`
  stops at the top level). `.git` folders are never
  walked, and directory links are never followed.
- `--json` prints the result as JSON, and
  `--stdin` checks one HTML document read from
  standard input.

## Who it is for

Every site owner and every developer who ships
HTML pages. A page shared without Open Graph tags
shows as a bare link with no title, no
description and no image — the share looks
broken and nobody clicks it, and the author only
finds out when someone else shares the page.
This is the gate that keeps the three tags in
place at the pull request.

## What it does NOT do

- It does not check what the tags point at — it
  never fetches an `og:image` URL, never checks
  the image exists or is the right size, and
  never checks that a title or description reads
  well. That is a different job.
- It does not check `<meta name="description">` —
  that job is repo #120
  (html-meta-description-checker-cli). The Open
  Graph tags are a different tag set on the same
  pages.
- It does not check `<title>` — that is repo #50,
  html-title-checker-cli. A page title is a
  different tag from `og:title`.
- It does not check Twitter card tags
  (`twitter:title` and friends) — only the three
  Open Graph tags listed above.
- It does not add a missing tag for you. It only
  reports the tags that are missing.
- It never rewrites a file, and it never touches
  the network.

## How this differs

- A fresh search of GitHub on Nov 17, 2026 found 0
  results for `"html-og-tag-checker-cli"` and 2
  results for `html og tag checker`, both web
  tools, none a local-file CLI gate —
  shayaneali/seo-meta-tag-checker, 0 stars (paste
  HTML or a URL, get a score out of 100 — a web
  tool); Ekanshps/OG-Preview, 0 stars (an Open
  Graph preview and checker web app — inspect
  metadata, preview social cards, generate tags;
  not a local-file gate).
- No rival checks Open Graph tags in local HTML
  files with a CI exit code.

## Install

```sh
git clone https://github.com/haiderstudio/html-og-tag-checker-cli.git
cd html-og-tag-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one HTML file:

```sh
python3 src/html_og_tag_checker.py page.html
```

A file with all three tags passes:

```sh
$ python3 src/html_og_tag_checker.py examples/clean.html
OK — 1 file(s) checked, every Open Graph tag is present.
```

A file with tags missing fails, with the file and
line for each one:

```sh
$ python3 src/html_og_tag_checker.py examples/flagged.html
FAIL examples/flagged.html: line 3 og tag "og:description" is missing
FAIL examples/flagged.html: line 3 og tag "og:image" is missing
Checked 1 file(s), 2 og tag(s) missing in 1 file(s).
```

Check a whole folder (`.html` and `.htm` files only):

```sh
$ python3 src/html_og_tag_checker.py examples/
FAIL examples/flagged.html: line 3 og tag "og:description" is missing
FAIL examples/flagged.html: line 3 og tag "og:image" is missing
Checked 3 file(s), 2 og tag(s) missing in 1 file(s).
```

Check one document from standard input:

```sh
$ printf '<html><head><title>t</title></head><body>x</body></html>\n' | python3 src/html_og_tag_checker.py --stdin
FAIL <stdin>: line 1 og tag "og:title" is missing
FAIL <stdin>: line 1 og tag "og:description" is missing
FAIL <stdin>: line 1 og tag "og:image" is missing
Checked 1 file(s), 3 og tag(s) missing in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/html_og_tag_checker.py --json examples/flagged.html
{
  "files": [
    {
      "path": "examples/flagged.html",
      "findings": [
        {
          "line": 3,
          "reason": "og tag \"og:description\" is missing"
        },
        {
          "line": 3,
          "reason": "og tag \"og:image\" is missing"
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "findings": 2
}
```

Exit codes: 0 when every tag is present, 1 when
any tag is missing or a file cannot be read, 2 for
a usage error (a missing path, a bad flag, or no
HTML files found).

## Examples

A page where the tags are there but unusual —
`examples/edge.html` uses capital letters in
`OG:TITLE`, holds an empty description, and
carries a second description tag inside a
comment. Presence only is checked, so it passes:

```sh
$ python3 src/html_og_tag_checker.py examples/edge.html
OK — 1 file(s) checked, every Open Graph tag is present.
```

A `<meta name="description">` tag does not count
as `og:description` — the two are different
tags, and a page with only the `name` version
still fails on the missing `og:description`.

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_html_og_tag_checker.py
```

The tests run the real CLI on throwaway files and
folders, check the bundled examples against their
saved output, and check every command quoted in
this README by running it.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool is original work, written for this
repository. It builds on the Python standard
library only (`html.parser`). The idea was
researched against GitHub on Nov 17, 2026 — no
existing tool does this exact job, as noted above
under "How this differs".
