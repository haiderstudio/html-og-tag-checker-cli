# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the HTML files you point it at, and it never rewrites a file and never changes anything. It writes nothing except the report on standard output (and usage errors on standard error). It never fetches a URL.

It only checks that the three Open Graph tags are present. It never adds a tag, never deletes a tag, and never runs code found in an HTML file.

If you find a case where the tool rewrites a file, opens a URL, or reports a pass for an HTML file missing an Open Graph tag, please open an issue describing the exact commands and input. Do not include any real secret in the report.
