"""Build docs/index.html for GitHub Pages (PyScript / Pyodide).

Extracts core logic from passguard/__init__.py via the ast module,
wraps it in a PyScript-powered cyberpunk HTML page, and writes to docs/.

Usage:
    python build_docs.py
"""

import ast
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "passguard" / "__init__.py"
OUT = ROOT / "docs" / "index.html"

PYSCRIPT_VERSION = "2024.9.2"


# ── AST extraction ────────────────────────────────────────────────────────


def _extract(source: str, tree: ast.Module, name: str) -> str:
    """Return the source text of a top-level assignment or function."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(source, node)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.get_source_segment(source, node)
    raise ValueError(f"{name!r} not found in source")


# ── Python code that runs inside PyScript ─────────────────────────────────

_PY_IMPORTS = """\
import hashlib
import math
import re
import secrets
import string
import asyncio

from pyscript import when, document, window
from pyodide.http import pyfetch
from js import navigator
"""

_PY_BROWSER = r'''
# ── Browser-specific breach check (async pyfetch, no requests needed) ──

async def check_breach(password):
    """HIBP k-anonymity check via pyfetch."""
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    resp = await pyfetch(f"https://api.pwnedpasswords.com/range/{prefix}")
    text = await resp.string()
    for line in text.splitlines():
        hash_suffix, count = line.split(":")
        if hash_suffix == suffix:
            return int(count)
    return 0


# ── Score-to-visual mapping ──

SCORE_MAP = [
    {"label": "Very Weak",  "pct": 20,  "color": "#ff003c", "glow": "rgba(255,0,60,0.15)"},
    {"label": "Weak",       "pct": 40,  "color": "#ff003c", "glow": "rgba(255,0,60,0.15)"},
    {"label": "Fair",       "pct": 60,  "color": "#ffae00", "glow": "rgba(255,174,0,0.15)"},
    {"label": "Strong",     "pct": 80,  "color": "#00f0ff", "glow": "rgba(0,240,255,0.2)"},
    {"label": "Very Strong","pct": 100, "color": "#00f0ff", "glow": "rgba(0,240,255,0.2)"},
]


# ── DOM helpers ──

def update_strength(password):
    """Run score_strength and update all UI elements."""
    bar = document.querySelector("#strengthBar")
    label_el = document.querySelector("#strengthText")
    pct_el = document.querySelector("#strengthPercent")
    panel = document.querySelector("#mainPanel")
    warn_el = document.querySelector("#warningsArea")

    criteria = {
        "c-length": len(password) >= 8,
        "c-upper": bool(re.search(r"[A-Z]", password)),
        "c-number": bool(re.search(r"\d", password)),
        "c-symbol": bool(re.search(r"[^a-zA-Z\d]", password)),
    }
    for cid, met in criteria.items():
        el = document.querySelector(f"#{cid}")
        if met:
            el.classList.add("active")
        else:
            el.classList.remove("active")

    if not password:
        bar.style.width = "0%"
        bar.style.background = "transparent"
        bar.style.boxShadow = "none"
        label_el.textContent = ""
        pct_el.textContent = ""
        panel.style.boxShadow = (
            "0 40px 80px rgba(0,0,0,0.6),"
            " inset 0 0 0 1px rgba(255,255,255,0.05)"
        )
        panel.style.borderColor = "rgba(255,255,255,0.08)"
        warn_el.innerHTML = ""
        return

    report = score_strength(password)
    s = SCORE_MAP[report["score"]]

    bar.style.width = f"{s['pct']}%"
    bar.style.background = s["color"]
    bar.style.boxShadow = f"0 0 15px {s['color']}"

    label_el.textContent = s["label"]
    label_el.style.color = s["color"]
    pct_el.textContent = f"{s['pct']:02d}%"

    panel.style.boxShadow = (
        f"0 40px 80px rgba(0,0,0,0.6),"
        f" 0 0 100px {s['glow']},"
        f" inset 0 0 0 1px rgba(255,255,255,0.05)"
    )
    panel.style.borderColor = s["color"]

    html = ""
    for w in report["warnings"]:
        html += f'<div class="warning-item">{w}</div>'
    warn_el.innerHTML = html


# ── Event handlers ──

@when("input", "#passwordInput")
def on_password_input(event):
    update_strength(event.target.value)
    document.querySelector("#breachResult").innerHTML = ""


@when("keydown", "#passwordInput")
def on_password_keydown(event):
    if event.key == "Enter":
        document.querySelector("#breachCheckBtn").click()


@when("click", "#breachCheckBtn")
async def on_breach_check(event):
    pwd = document.querySelector("#passwordInput").value
    result_el = document.querySelector("#breachResult")
    btn = document.querySelector("#breachCheckBtn")

    if not pwd:
        result_el.innerHTML = (
            '<div class="warning-item">Enter a password first</div>'
        )
        return

    btn.textContent = "CHECKING..."
    btn.disabled = True
    try:
        count = await check_breach(pwd)
        if count:
            s = "es" if count != 1 else ""
            result_el.innerHTML = (
                '<div class="breach-result breach-danger">'
                f'Breached! Found in {count:,} data breach{s}. '
                'Change it immediately.</div>'
            )
        else:
            result_el.innerHTML = (
                '<div class="breach-result breach-safe">'
                'Safe! Not found in any known data breaches.</div>'
            )
    except Exception as e:
        result_el.innerHTML = (
            '<div class="breach-result breach-danger">'
            f'Connection error: {e}</div>'
        )
    finally:
        btn.textContent = "CHECK ONLINE DATABASE"
        btn.disabled = False


@when("click", "#generateBtn")
def on_generate(event):
    length = int(document.querySelector("#lengthSlider").value)
    upper = document.querySelector("#optUppercase").checked
    digits = document.querySelector("#optDigits").checked
    symbols = document.querySelector("#optSymbols").checked

    pwd = generate_password(
        length, uppercase=upper, digits=digits, symbols=symbols,
    )
    report = score_strength(pwd)
    s = SCORE_MAP[report["score"]]

    out = document.querySelector("#generateOutput")
    out.style.display = "block"
    document.querySelector("#generatedPassword").textContent = pwd
    document.querySelector("#genStrength").innerHTML = (
        f'<span style="color:{s["color"]}">{s["label"]}</span>'
        f' &middot; {report["entropy"]} bits'
    )


@when("click", "#copyBtn")
async def on_copy(event):
    text = document.querySelector("#generatedPassword").textContent
    btn = event.target
    try:
        await navigator.clipboard.writeText(text)
        btn.textContent = "COPIED!"
        await asyncio.sleep(1.5)
        btn.textContent = "COPY"
    except Exception:
        pass


# ── Ready — hide loading overlay & pre-generate a password ──
document.querySelector("#loading-overlay").style.display = "none"
document.querySelector("#generateBtn").click()
'''


# ── HTML template ─────────────────────────────────────────────────────────
# Uses __PYSCRIPT_VERSION__ and __PYSCRIPT_CODE__ as placeholders
# (no f-strings or .format to avoid escaping CSS/JS braces).

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Assistant</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24' fill='none' stroke='%23153036' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z'/%3E%3C/svg%3E">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://pyscript.net/releases/__PYSCRIPT_VERSION__/core.css">
    <script type="module" src="https://pyscript.net/releases/__PYSCRIPT_VERSION__/core.js"></script>
    <style>
        :root {
            --bg-base: #050505;
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.08);
            --ui-accent: #ffffff;
            --text-muted: #666;
            --low-glow: #ff003c;
            --mid-glow: #ffae00;
            --high-glow: #00f0ff;
            --row-color-1: #1a1a1a;
            --row-color-2: #222222;
            --row-color-3: #151515;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body, html {
            height: 100%;
            width: 100%;
            background-color: var(--bg-base);
            background-image: radial-gradient(circle at center, transparent 0%, #000000 100%);
            font-family: 'Inter', -apple-system, sans-serif;
            overflow-x: hidden;
            overflow-y: auto;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--ui-accent);
        }

        /* ── Loading overlay ── */
        #loading-overlay {
            position: fixed;
            inset: 0;
            z-index: 9999;
            background: var(--bg-base);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 1.5rem;
        }
        #loading-overlay .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255,255,255,0.1);
            border-top-color: var(--high-glow);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        #loading-overlay p {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 3px;
            color: var(--text-muted);
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* ── Kinetic background ── */
        .background-wrapper {
            position: fixed;
            top: -25%; left: -25%;
            width: 150%; height: 150%;
            z-index: 1;
            transform: rotate(-6deg);
            display: flex;
            flex-direction: column;
            justify-content: center;
            pointer-events: none;
            user-select: none;
        }
        .row {
            display: flex;
            white-space: nowrap;
            overflow: hidden;
            width: 100%;
            margin-top: -5rem;
            flex-shrink: 0;
        }
        .ticker {
            display: inline-block;
            font-weight: 900;
            text-transform: uppercase;
            line-height: 1.4;
            will-change: transform;
        }
        .row:nth-child(3n+1) .ticker { color: var(--row-color-1); }
        .row:nth-child(3n+2) .ticker { color: var(--row-color-2); }
        .row:nth-child(3n+3) .ticker { color: var(--row-color-3); }
        .animate-left  { animation: scrollLeft  linear infinite; }
        .animate-right { animation: scrollRight linear infinite; }
        @keyframes scrollLeft  { 0% { transform: translateX(0);    } 100% { transform: translateX(-50%); } }
        @keyframes scrollRight { 0% { transform: translateX(-50%); } 100% { transform: translateX(0);    } }

        /* ── Glass panel ── */
        .glass-panel {
            position: relative;
            z-index: 10;
            width: 20%;
            max-width: 720px;
            padding: 3rem 2rem 2rem;
            margin: 2rem 0;
            background: var(--glass-bg);
            backdrop-filter: blur(25px);
            -webkit-backdrop-filter: blur(25px);
            border-radius: 24px;
            border: 1px solid var(--glass-border);
            box-shadow:
                0 40px 80px rgba(0, 0, 0, 0.6),
                inset 0 0 0 1px rgba(255, 255, 255, 0.05);
            transition: box-shadow 0.5s ease, border-color 0.5s ease;
        }

        /* ── Header ── */
        .header { margin-bottom: 2rem; }
        .header h1 {
            font-size: 1.6rem;
            font-weight: 700;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .header h1 svg { flex-shrink: 0; }
        .header p {
            font-size: 0.65rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 3px;
            font-weight: 500;
            margin-top: 0.4rem;
        }

        /* ── Tabs ── */
        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 2rem;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            padding: 4px;
        }
        .tab {
            flex: 1;
            padding: 0.55rem 0.8rem;
            background: transparent;
            border: none;
            color: #555;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.3s ease;
            font-family: inherit;
        }
        .tab:hover { color: #888; }
        .tab.active {
            background: rgba(255,255,255,0.08);
            color: #fff;
        }

        /* ── Password input ── */
        .input-wrapper {
            position: relative;
            margin-bottom: 1.5rem;
        }
        #passwordInput {
            width: 100%;
            padding: 0.9rem 2.5rem 0.9rem 0;
            background: transparent;
            border: none;
            border-bottom: 2px solid #333;
            font-size: 1.3rem;
            color: var(--ui-accent);
            outline: none;
            letter-spacing: 2px;
            font-family: 'Space Grotesk', sans-serif;
            transition: border-color 0.4s ease;
        }
        #passwordInput::placeholder {
            letter-spacing: 1px;
            color: #444;
            font-weight: 400;
            font-family: 'Inter', -apple-system, sans-serif;
        }
        #passwordInput:focus { border-bottom-color: #666; }
        .toggle-vis {
            position: absolute;
            right: 0;
            top: 50%;
            transform: translateY(-75%);
            background: none;
            border: none;
            color: #555;
            cursor: pointer;
            padding: 4px;
            display: flex;
            transition: color 0.3s ease;
        }
        .toggle-vis:hover { color: #999; }

        /* ── Strength bar ── */
        .strength-bar-container {
            position: absolute;
            bottom: -2px; left: 0;
            width: 100%; height: 2px;
            overflow: hidden;
            border-radius: 2px;
        }
        .strength-bar {
            height: 100%;
            width: 0%;
            background: transparent;
            transition:
                width 0.6s cubic-bezier(0.22, 1, 0.36, 1),
                background 0.4s ease,
                box-shadow 0.4s ease;
        }
        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 1rem;
        }
        #strengthText {
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #555;
            transition: color 0.4s ease;
        }
        #strengthPercent {
            font-family: 'Courier New', monospace;
            font-size: 0.8rem;
            font-weight: 600;
            color: #444;
        }

        /* ── Criteria grid ── */
        .criteria {
            margin-top: 2rem;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
        }
        .criterion {
            font-size: 0.7rem;
            color: #555;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: all 0.4s ease;
            font-weight: 500;
        }
        .criterion.active {
            color: var(--ui-accent);
            text-shadow: 0 0 10px rgba(255,255,255,0.2);
        }
        .check-box {
            width: 14px; height: 14px;
            border-radius: 3px;
            border: 1.5px solid #333;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            flex-shrink: 0;
        }
        .criterion.active .check-box {
            background: var(--ui-accent);
            border-color: var(--ui-accent);
            box-shadow: 0 0 10px rgba(255, 255, 255, 0.4);
        }
        .check-box::after {
            content: '';
            width: 4px; height: 7px;
            border: solid black;
            border-width: 0 1.5px 1.5px 0;
            transform: rotate(45deg);
            display: none;
        }
        .criterion.active .check-box::after { display: block; }

        /* ── Warnings ── */
        #warningsArea { margin-top: 1.2rem; }
        .warning-item {
            padding: 0.45rem 0.8rem;
            margin-top: 0.5rem;
            font-size: 0.65rem;
            color: var(--mid-glow);
            border-left: 2px solid var(--mid-glow);
            background: rgba(255,174,0,0.04);
            border-radius: 0 4px 4px 0;
        }

        /* ── Action buttons ── */
        .action-btn {
            width: 100%;
            padding: 0.85rem;
            margin-top: 1.8rem;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 2px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: inherit;
        }
        .action-btn:hover {
            background: rgba(255,255,255,0.1);
            border-color: rgba(255,255,255,0.2);
        }
        .action-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* ── Breach results ── */
        .breach-result {
            padding: 0.7rem 1rem;
            margin-top: 1rem;
            font-size: 0.7rem;
            font-weight: 500;
            border-radius: 6px;
            line-height: 1.5;
        }
        .breach-safe {
            color: var(--high-glow);
            border: 1px solid rgba(0,240,255,0.2);
            background: rgba(0,240,255,0.04);
        }
        .breach-danger {
            color: var(--low-glow);
            border: 1px solid rgba(255,0,60,0.2);
            background: rgba(255,0,60,0.04);
        }

        /* ── Generate view ── */
        .slider-group { margin-bottom: 1.5rem; }
        .slider-group label {
            display: flex;
            justify-content: space-between;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #888;
            margin-bottom: 0.8rem;
        }
        .slider-group label span {
            color: var(--high-glow);
            font-family: 'Courier New', monospace;
        }
        input[type="range"] {
            -webkit-appearance: none;
            width: 100%;
            height: 4px;
            background: #222;
            border-radius: 2px;
            outline: none;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 16px; height: 16px;
            background: var(--ui-accent);
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 0 8px rgba(255,255,255,0.3);
        }
        input[type="range"]::-moz-range-thumb {
            width: 16px; height: 16px;
            background: var(--ui-accent);
            border: none;
            border-radius: 50%;
            cursor: pointer;
        }

        .checkbox-group {
            display: flex;
            gap: 1.2rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }
        .checkbox-group label {
            font-size: 0.7rem;
            color: #888;
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            font-weight: 500;
        }
        .checkbox-group input[type="checkbox"] {
            accent-color: var(--high-glow);
            width: 14px; height: 14px;
            cursor: pointer;
        }

        /* ── Password output ── */
        .password-output {
            margin-top: 1.2rem;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }
        .password-output code {
            flex: 1;
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
            color: var(--ui-accent);
            word-break: break-all;
            letter-spacing: 1px;
        }
        .copy-btn {
            padding: 0.4rem 0.8rem;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.15);
            color: #fff;
            font-size: 0.6rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
            font-family: inherit;
        }
        .copy-btn:hover {
            background: rgba(255,255,255,0.15);
        }
        #genStrength {
            margin-top: 0.8rem;
            font-size: 0.7rem;
            color: #888;
        }

        /* ── Tab content (grid-stack keeps panel height stable) ── */
        .tab-content-wrapper {
            display: grid;
        }
        .tab-content-wrapper > .tab-content {
            grid-area: 1 / 1;
            visibility: hidden;
        }
        .tab-content-wrapper > .tab-content.active {
            visibility: visible;
        }
        /* Kill child transitions so visibility switches instantly */
        .tab-content-wrapper > .tab-content:not(.active),
        .tab-content-wrapper > .tab-content:not(.active) * {
            visibility: hidden !important;
            transition: none !important;
        }

        #breachResult { min-height: 4rem; }

        /* ── Privacy note ── */
        .privacy-note {
            margin-top: 2rem;
            padding-top: 1.2rem;
            border-top: 1px solid rgba(255,255,255,0.08);
            font-size: 0.75rem;
            color: #999;
            line-height: 1.6;
        }
        .privacy-note a { color: #ccc; }

        /* ── Responsive ── */
        @media (max-width: 600px) {
            .glass-panel { padding: 2rem 1.5rem 1.8rem; }
            .background-wrapper { top: -10%; left: -10%; width: 120%; }
            .ticker { font-size: 8rem; }
            .header h1 { font-size: 1.3rem; }
        }

        /* ── Hide PyScript default UI ── */
        py-script, script[type="py"] { display: none; }
    </style>
</head>
<body>

    <!-- Loading overlay -->
    <div id="loading-overlay">
        <div class="spinner"></div>
        <p>Initializing</p>
    </div>

    <!-- Kinetic background -->
    <div class="background-wrapper" id="bgRows"></div>

    <!-- Main UI -->
    <div class="glass-panel" id="mainPanel">
        <div class="header">
            <h1>
                <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24"
                     fill="none" stroke="currentColor" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>
                </svg>
                Password Assistant
            </h1>
            <p>User-side Password Assistant</p>
        </div>

        <!-- Tabs -->
        <div class="tabs">
            <button class="tab active" data-tab="check">Check Password</button>
            <button class="tab" data-tab="generate">Generate Password</button>
        </div>

        <div class="tab-content-wrapper">
        <!-- ═══ Check view ═══ -->
        <div id="checkView" class="tab-content active">
            <div class="input-wrapper">
                <input type="text" id="passwordInput"
                       placeholder="Enter password..." spellcheck="false" autocomplete="off">
                <button type="button" class="toggle-vis" id="toggleVis" aria-label="Toggle password visibility">
                    <svg id="eyeOpen" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                         fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/>
                        <circle cx="12" cy="12" r="3"/>
                    </svg>
                    <svg id="eyeClosed" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                         fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                         style="display:none">
                        <path d="m15 18-.722-3.25"/>
                        <path d="M2 8a10.645 10.645 0 0 0 20 0"/>
                        <path d="m20 15-1.726-2.05"/>
                        <path d="m4 15 1.726-2.05"/>
                        <path d="m9 18 .722-3.25"/>
                    </svg>
                </button>
                <div class="strength-bar-container">
                    <div class="strength-bar" id="strengthBar"></div>
                </div>
                <div class="status-row">
                    <span id="strengthText"></span>
                    <span id="strengthPercent"></span>
                </div>
            </div>

            <div class="criteria">
                <div class="criterion" id="c-length"><div class="check-box"></div>8+ Chars</div>
                <div class="criterion" id="c-upper"><div class="check-box"></div>Uppercase</div>
                <div class="criterion" id="c-number"><div class="check-box"></div>Numerals</div>
                <div class="criterion" id="c-symbol"><div class="check-box"></div>Symbols</div>
            </div>

            <div id="warningsArea"></div>

            <button id="breachCheckBtn" class="action-btn">Check Online Database</button>
            <div id="breachResult"></div>
        </div>

        <!-- ═══ Generate view ═══ -->
        <div id="generateView" class="tab-content">
            <div class="slider-group">
                <label>Length <span id="lengthValue">16</span></label>
                <input type="range" id="lengthSlider" min="8" max="64" value="16">
            </div>

            <div class="checkbox-group">
                <label><input type="checkbox" id="optUppercase" checked> Uppercase</label>
                <label><input type="checkbox" id="optDigits" checked> Digits</label>
                <label><input type="checkbox" id="optSymbols" checked> Symbols</label>
            </div>

            <button id="generateBtn" class="action-btn">Generate Password</button>

            <div id="generateOutput" style="display:none">
                <div class="password-output">
                    <code id="generatedPassword"></code>
                    <button id="copyBtn" class="copy-btn">Copy</button>
                </div>
                <div id="genStrength"></div>
            </div>
        </div>
        </div><!-- /tab-content-wrapper -->

        <div class="privacy-note">
            Your password never leaves your browser. Breach checks use 
            <a href="https://en.wikipedia.org/wiki/K-anonymity" target="_blank"
               rel="noopener">k-anonymity</a>
               <p>
                This means that only the first five characters of the SHA-1 hash are sent.
                <p>
        </div>
    </div>

    <!-- Background animation + tab switching + controls (pure JS, instant) -->
    <script>
        // ╔══════════════════════════════════════════════════════════════╗
        // ║  BACKGROUND CONFIG — all animation knobs in one place      ║
        // ╚══════════════════════════════════════════════════════════════╝
        const BG = {
            words:       ["PASSWORD123","SERIOUSLY_SAFE","PROBABLY_SAFE","ACCESS_DENIED","TOTALLY_SECURE","QWERTY","REALLY_SAFE"],
            rows:        33,           // number of scrolling rows
            wordsPerRow: 7,           // random words picked per row
            repeats:     30,          // times the word set is repeated (seamless loop)
            speed:       9000,        // base animation duration (seconds)
            variance:    0.5,        // speed randomness (0 = uniform, 1 = wild)
            fontSize:    "clamp(8rem, 15vw, 16rem)",
            letterGap:   "0px",      // letter-spacing
            wordGap:     "50px",      // padding-right between repeated blocks
            rowPadding:  "0.1vh",       // vertical padding per row
        };

        // ── Build rows ──
        const bgRows = document.getElementById('bgRows');
        for (let i = 0; i < BG.rows; i++) {
            const row = document.createElement('div');
            row.className = 'row';
            row.style.padding = `${BG.rowPadding} 0`;
            const ticker = document.createElement('div');
            ticker.className = `ticker ${i % 2 === 0 ? 'animate-left' : 'animate-right'}`;
            const v = BG.speed * BG.variance;
            ticker.style.animationDuration = `${BG.speed + (Math.random() * v * 2 - v)}s`;
            ticker.style.fontSize = BG.fontSize;
            ticker.style.letterSpacing = BG.letterGap;
            ticker.style.paddingRight = BG.wordGap;
            const words = [...BG.words].sort(() => 0.5 - Math.random()).slice(0, BG.wordsPerRow).join("  ");
            ticker.innerText = (words + " ").repeat(BG.repeats);
            row.appendChild(ticker);
            bgRows.appendChild(row);
        }

        // ── Tab switching ──
        document.querySelectorAll('.tab').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(btn.dataset.tab + 'View').classList.add('active');
                if (btn.dataset.tab === 'generate') {
                    document.getElementById('generateBtn').click();
                }
            });
        });

        // ── Slider value display ──
        const slider = document.getElementById('lengthSlider');
        const sliderVal = document.getElementById('lengthValue');
        slider.addEventListener('input', () => { sliderVal.textContent = slider.value; });

        // ── Password visibility toggle ──
        document.getElementById('toggleVis').addEventListener('click', () => {
            const inp = document.getElementById('passwordInput');
            const isText = inp.type === 'text';
            inp.type = isText ? 'password' : 'text';
            document.getElementById('eyeOpen').style.display = isText ? 'none' : '';
            document.getElementById('eyeClosed').style.display = isText ? '' : 'none';
        });
    </script>

    <!-- Python logic via PyScript -->
    <script type="py">
__PYSCRIPT_CODE__
    </script>

</body>
</html>
'''


# ── Build ──────────────────────────────────────────────────────────────────


def build() -> None:
    source = SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)

    sequences = _extract(source, tree, "_SEQUENCES")
    score_fn = _extract(source, tree, "score_strength")
    generate_fn = _extract(source, tree, "generate_password")

    py_code = (
        _PY_IMPORTS
        + "\n# ── Core logic (extracted from passguard/__init__.py) ──\n\n"
        + sequences + "\n\n"
        + score_fn + "\n\n"
        + generate_fn + "\n"
        + _PY_BROWSER
    )

    html = (
        HTML_TEMPLATE
        .replace("__PYSCRIPT_VERSION__", PYSCRIPT_VERSION)
        .replace("__PYSCRIPT_CODE__", py_code)
    )

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"Built {OUT}  ({len(html):,} bytes)")


if __name__ == "__main__":
    build()
