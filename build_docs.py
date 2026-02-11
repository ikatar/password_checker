"""Build docs/index.html for GitHub Pages (stlite / Pyodide).

Combines the passguard core logic and the Streamlit UI into a single
self-contained Python source, then embeds it in an HTML page that
loads stlite to run the app entirely in the browser.

Usage:
    python build_docs.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
STLITE_VERSION = "0.73.0"

# Double-braces {{}} are literal braces in the output;
# {version} and {source} are replaced by str.format().
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Password Assistant</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24' fill='none' stroke='%234A90D9' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z'/%3E%3C/svg%3E" />
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/@stlite/mountable@{version}/build/stlite.css"
    />
  </head>
  <body>
    <div id="root"></div>
    <script src="https://cdn.jsdelivr.net/npm/@stlite/mountable@{version}/build/stlite.js"></script>
    <script>
      stlite.mount(
        {{
          requirements: ["pyodide-http", "requests"],
          entrypoint: "app.py",
          files: {{
            "app.py": {source},
          }},
        }},
        document.getElementById("root")
      );
    </script>
  </body>
</html>
"""


def _strip_header(source: str) -> str:
    """Remove the leading docstring, import lines, and blank lines."""
    lines = source.splitlines(keepends=True)
    result: list[str] = []
    in_docstring = False
    past_header = False

    for line in lines:
        stripped = line.strip()

        # Skip module-level docstring
        if not past_header and not in_docstring and stripped.startswith('"""'):
            if stripped.count('"""') >= 2:
                continue  # single-line docstring
            in_docstring = True
            continue
        if in_docstring:
            if '"""' in stripped:
                in_docstring = False
            continue

        # Skip top-level imports
        if not past_header and re.match(r"^(import |from )", stripped):
            continue

        # Skip leading blank lines
        if not past_header and not stripped:
            continue

        past_header = True
        result.append(line)

    return "".join(result)


def build() -> None:
    core_src = (ROOT / "passguard" / "__init__.py").read_text(encoding="utf-8")
    app_src = (ROOT / "app.py").read_text(encoding="utf-8")

    core_body = _strip_header(core_src)
    app_body = _strip_header(app_src)

    # Assemble the standalone source with pyodide-http patch
    combined = (
        "import hashlib\n"
        "import math\n"
        "import re\n"
        "import secrets\n"
        "import string\n\n"
        "try:\n"
        "    import pyodide_http\n"
        "    pyodide_http.patch_all()\n"
        "except ImportError:\n"
        "    pass\n\n"
        "import requests\n"
        "import streamlit as st\n\n"
        + core_body
        + "\n"
        + app_body
    )

    # json.dumps handles all JS string escaping
    js_source = json.dumps(combined)
    html = HTML_TEMPLATE.format(version=STLITE_VERSION, source=js_source)

    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Built {out} ({len(html):,} bytes)")


if __name__ == "__main__":
    build()
