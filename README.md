# PassGuard

A client-side password security tool with a CLI and a browser UI hosted on GitHub Pages.

**Live demo:** [https://ikatar.github.io/password_checker/](https://ikatar.github.io/password_checker/)

## Features

- **Breach checking** -- queries Have I Been Pwned using k-anonymity (only the first 5 characters of the SHA-1 hash are sent; your password never leaves the client)
- **Strength analysis** -- entropy calculation, character-class detection, sequential/repeated pattern warnings, composite 0-4 score
- **Password generation** -- cryptographically secure (`secrets` module), configurable length and character classes

## Quick start

### CLI

```bash
pip install -r requirements.txt

# Check a password
python -m passguard check mypassword --strength

# Generate passwords
python -m passguard generate -n 20 -c 5
```

### Web UI

The browser UI runs entirely client-side via [PyScript](https://pyscript.net/) (Pyodide). No server needed.

```bash
python build_docs.py          # generates docs/index.html
# open docs/index.html in a browser
```

GitHub Pages serves `docs/index.html` automatically on push.

## Project structure

```
passguard/
  __init__.py      # core logic (breach check, strength, generator) -- single source of truth
  cli.py           # CLI entry point
  __main__.py      # python -m passguard
build_docs.py      # AST-extracts core logic, embeds in PyScript HTML template
docs/
  index.html       # generated -- cyberpunk UI with PyScript (do not edit manually)
tests/
  test_checker.py  # pytest suite
requirements.txt   # requests, pytest
```

## How the build works

`build_docs.py` uses Python's `ast` module to extract `_SEQUENCES`, `score_strength`, and `generate_password` from `passguard/__init__.py` at build time. It combines them with a browser-specific async `check_breach` (using Pyodide's `pyfetch` instead of `requests`) and embeds everything in a `<script type="py">` block inside the cyberpunk HTML template. This keeps `passguard/__init__.py` as the single source of truth -- edit logic there, then regenerate with `python build_docs.py`.

## Tests

```bash
python -m pytest tests/ -v
```
