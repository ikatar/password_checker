"""PassGuard -- password security utilities.

Core functions for breach checking, strength analysis, password generation,
and email breach exposure checking.
"""

import hashlib
import math
import re
import secrets
import string

import requests


# ── Breach checking (HIBP k-anonymity) ─────────────────────────────────────


def check_breach(password: str) -> int:
    """Return the number of times *password* appears in known data breaches.

    Only the first 5 characters of the SHA-1 hash are sent over the network
    (k-anonymity).  The full hash never leaves the client.
    """
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    resp = requests.get(
        f"https://api.pwnedpasswords.com/range/{prefix}",
        timeout=10,
    )
    resp.raise_for_status()

    for line in resp.text.splitlines():
        hash_suffix, count = line.split(":")
        if hash_suffix == suffix:
            return int(count)
    return 0


# ── Email breach checking (XposedOrNot + LeakCheck) ──────────────────────


def check_email_breach(email: str) -> dict:
    """Check if *email* appears in known data breaches.

    Queries XposedOrNot and LeakCheck (both free, keyless).
    Returns a dict with keys: exposed, breaches, sources_checked, errors.
    """
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return {
            "exposed": False,
            "breaches": [],
            "sources_checked": [],
            "errors": [f"Invalid email address: {email}"],
        }

    breaches: dict[str, dict] = {}
    errors: list[str] = []
    sources_checked: list[str] = []

    # ── XposedOrNot ──
    try:
        resp = requests.get(
            f"https://api.xposedornot.com/v1/check-email/{email}",
            timeout=10,
        )
        if resp.status_code == 404:
            # Not found — not an error, just no breaches
            sources_checked.append("XposedOrNot")
        else:
            resp.raise_for_status()
            data = resp.json()
            # Response format: {"breaches": [["Name1","Name2",...]]}
            # — a list containing one flat list of breach name strings.
            raw = data.get("breaches", [])
            names = []
            for item in raw:
                if isinstance(item, list):
                    names.extend(item)
                else:
                    names.append(str(item))
            for name in names:
                key = name.lower()
                if key not in breaches:
                    breaches[key] = {
                        "name": name,
                        "date": None,
                        "source": "XposedOrNot",
                    }
            sources_checked.append("XposedOrNot")
    except Exception as exc:
        errors.append(f"XposedOrNot: {exc}")

    # ── LeakCheck ──
    try:
        resp = requests.get(
            f"https://leakcheck.io/api/public?check={email}",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") and data.get("found", 0) > 0:
            for src in data.get("sources", []):
                name = src.get("name", "Unknown")
                key = name.lower()
                # Prefer LeakCheck entry (has date) over XposedOrNot
                breaches[key] = {
                    "name": name,
                    "date": src.get("date"),
                    "source": "LeakCheck",
                }
        sources_checked.append("LeakCheck")
    except Exception as exc:
        errors.append(f"LeakCheck: {exc}")

    return {
        "exposed": len(breaches) > 0,
        "breaches": list(breaches.values()),
        "sources_checked": sources_checked,
        "errors": errors,
    }


# ── Strength analysis ──────────────────────────────────────────────────────

_SEQUENCES = [
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
]


def score_strength(password: str) -> dict:
    """Analyse password strength and return a detailed report.

    Returns a dict with keys:
        length       -- int
        entropy      -- float (bits)
        char_classes -- dict[str, bool]  (lowercase, uppercase, digits, symbols)
        score        -- int 0-4  (0 = very weak ... 4 = very strong)
        label        -- str
        warnings     -- list[str]
    """
    warnings: list[str] = []

    # Character-class analysis
    classes = {
        "lowercase": bool(re.search(r"[a-z]", password)),
        "uppercase": bool(re.search(r"[A-Z]", password)),
        "digits":    bool(re.search(r"\d", password)),
        "symbols":   bool(re.search(r"[^a-zA-Z\d]", password)),
    }

    pool = sum([
        26 if classes["lowercase"] else 0,
        26 if classes["uppercase"] else 0,
        10 if classes["digits"] else 0,
        32 if classes["symbols"] else 0,
    ]) or 1

    entropy = len(password) * math.log2(pool) if password else 0.0

    # Pattern detection (skip for high-entropy passwords where
    # short sequences are statistically expected, not human-chosen)
    lower = password.lower()
    if entropy < 90:
        for seq in _SEQUENCES:
            for i in range(len(seq) - 2):
                chunk = seq[i : i + 3]
                if chunk in lower or chunk[::-1] in lower:
                    warnings.append(f"Sequential pattern detected ('{chunk}')")
                    break

    if re.search(r"(.)\1{2,}", password):
        warnings.append("Repeated characters detected (e.g. 'aaa')")

    if len(password) < 8:
        warnings.append("Too short -- use at least 8 characters")
    elif len(password) < 12:
        warnings.append("Consider using 12+ characters")

    # Deduplicate while preserving order
    warnings = list(dict.fromkeys(warnings))

    # Composite score
    class_count = sum(classes.values())
    high_entropy = entropy >= 90  # enough bits to override class-count gates
    if entropy < 28 or len(password) < 8:
        score = 0
    elif entropy < 36 or (not high_entropy and class_count < 2):
        score = 1
    elif entropy < 50 or (not high_entropy and class_count < 3):
        score = 2
    elif entropy < 65 and not high_entropy:
        score = 3
    else:
        score = 4

    labels = ["Very Weak", "Weak", "Fair", "Strong", "Very Strong"]

    return {
        "length": len(password),
        "entropy": round(entropy, 1),
        "char_classes": classes,
        "score": score,
        "label": labels[score],
        "warnings": warnings,
    }


# ── Password generation ────────────────────────────────────────────────────


def generate_password(
    length: int = 12,
    *,
    uppercase: bool = True,
    digits: bool = True,
    symbols: bool = True,
) -> str:
    """Generate a cryptographically secure random password.

    Guarantees at least one character from each enabled character class.
    Uses :mod:`secrets` for cryptographic randomness.
    """
    if length < 4:
        raise ValueError("Password length must be at least 4")

    alphabet = string.ascii_lowercase
    required = [secrets.choice(string.ascii_lowercase)]

    if uppercase:
        alphabet += string.ascii_uppercase
        required.append(secrets.choice(string.ascii_uppercase))
    if digits:
        alphabet += string.digits
        required.append(secrets.choice(string.digits))
    if symbols:
        alphabet += string.punctuation
        required.append(secrets.choice(string.punctuation))

    remaining = length - len(required)
    chars = required + [secrets.choice(alphabet) for _ in range(remaining)]

    # Fisher-Yates shuffle with cryptographic randomness
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]

    return "".join(chars)
