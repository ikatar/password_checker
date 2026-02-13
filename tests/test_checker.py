"""Tests for the passguard package."""

from unittest.mock import Mock, patch

import pytest

from passguard import check_breach, check_email_breach, generate_password, score_strength


# ── Fixtures / helpers ─────────────────────────────────────────────────────

# "password" SHA-1 = 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8
#   prefix = 5BAA6 , suffix = 1E4C9B93F3F0682250B6CF8331B7EE68FD8

HIBP_RESPONSE_HIT = (
    "0018A45C4D1DEF81644B54AB7F969B88D65:10\r\n"
    "00D4F6E8FA6EECAD2A3AA415EEC418D38EC:2\r\n"
    "1E4C9B93F3F0682250B6CF8331B7EE68FD8:3533661\r\n"
    "A0F78D8CD41C7B9B0C55B12E858CDEE2E8B:3\r\n"
)

HIBP_RESPONSE_MISS = (
    "0018A45C4D1DEF81644B54AB7F969B88D65:10\r\n"
    "00D4F6E8FA6EECAD2A3AA415EEC418D38EC:2\r\n"
    "A0F78D8CD41C7B9B0C55B12E858CDEE2E8B:3\r\n"
)


def _mock_response(text: str) -> Mock:
    resp = Mock()
    resp.text = text
    resp.raise_for_status = Mock()
    return resp


# ── check_breach ───────────────────────────────────────────────────────────


class TestCheckBreach:
    @patch("passguard.requests.get")
    def test_found(self, mock_get):
        mock_get.return_value = _mock_response(HIBP_RESPONSE_HIT)
        assert check_breach("password") == 3533661

    @patch("passguard.requests.get")
    def test_not_found(self, mock_get):
        mock_get.return_value = _mock_response(HIBP_RESPONSE_MISS)
        assert check_breach("password") == 0

    @patch("passguard.requests.get")
    def test_sends_only_prefix(self, mock_get):
        mock_get.return_value = _mock_response(HIBP_RESPONSE_MISS)
        check_breach("password")
        url = mock_get.call_args[0][0]
        assert url == "https://api.pwnedpasswords.com/range/5BAA6"
        # Full hash never sent
        assert "1E4C9B93F3F0682250B6CF8331B7EE68FD8" not in url

    @patch("passguard.requests.get")
    def test_api_error_propagates(self, mock_get):
        mock_get.return_value = Mock()
        mock_get.return_value.raise_for_status.side_effect = Exception("503")
        with pytest.raises(Exception, match="503"):
            check_breach("password")


# ── score_strength ─────────────────────────────────────────────────────────


class TestScoreStrength:
    def test_empty_password(self):
        r = score_strength("")
        assert r["score"] == 0
        assert r["entropy"] == 0.0
        assert r["length"] == 0

    def test_short_password(self):
        r = score_strength("abc")
        assert r["score"] == 0
        assert r["label"] == "Very Weak"
        assert any("short" in w.lower() for w in r["warnings"])

    def test_all_char_classes(self):
        r = score_strength("aB1!")
        c = r["char_classes"]
        assert c["lowercase"] is True
        assert c["uppercase"] is True
        assert c["digits"] is True
        assert c["symbols"] is True

    def test_strong_password(self):
        r = score_strength("Tr0ub4dor&3!xyzQ")
        assert r["score"] >= 3

    def test_sequential_warning(self):
        r = score_strength("abcdefgh12")
        assert any("Sequential" in w for w in r["warnings"])

    def test_reverse_sequential_warning(self):
        r = score_strength("zyxpassword")
        assert any("Sequential" in w for w in r["warnings"])

    def test_repeated_chars_warning(self):
        r = score_strength("aaabbbccc1")
        assert any("Repeated" in w for w in r["warnings"])

    def test_keyboard_pattern_warning(self):
        r = score_strength("qwertyABC1!")
        assert any("Sequential" in w for w in r["warnings"])

    def test_entropy_increases_with_length(self):
        short = score_strength("aB1!aB1!")
        long = score_strength("aB1!aB1!aB1!aB1!")
        assert long["entropy"] > short["entropy"]

    def test_entropy_increases_with_classes(self):
        lower_only = score_strength("abcdefghijkl")
        mixed = score_strength("aBcDeFgHiJkL")
        assert mixed["entropy"] > lower_only["entropy"]


# ── generate_password ──────────────────────────────────────────────────────


class TestGeneratePassword:
    def test_default_length(self):
        assert len(generate_password()) == 16

    def test_custom_length(self):
        assert len(generate_password(32)) == 32

    def test_minimum_length(self):
        assert len(generate_password(4)) == 4

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="at least 4"):
            generate_password(3)

    def test_contains_all_classes(self):
        for _ in range(20):
            pwd = generate_password(16)
            assert any(c.islower() for c in pwd)
            assert any(c.isupper() for c in pwd)
            assert any(c.isdigit() for c in pwd)
            assert any(not c.isalnum() for c in pwd)

    def test_no_symbols(self):
        for _ in range(20):
            pwd = generate_password(16, symbols=False)
            assert all(c.isalnum() for c in pwd)

    def test_no_uppercase(self):
        for _ in range(20):
            pwd = generate_password(16, uppercase=False)
            assert all(not c.isupper() for c in pwd)

    def test_no_digits(self):
        for _ in range(20):
            pwd = generate_password(16, digits=False)
            assert all(not c.isdigit() for c in pwd)

    def test_uniqueness(self):
        passwords = {generate_password() for _ in range(50)}
        assert len(passwords) == 50  # all unique


# ── check_email_breach ────────────────────────────────────────────────────

# Sample API responses
XON_FOUND = '{"breaches": [["Adobe", "LinkedIn"]], "status": "success"}'
XON_NOT_FOUND = '{"Error": "Not found"}'

LC_FOUND = '{"success": true, "found": 2, "sources": [{"name": "Adobe", "date": "2013-10"}, {"name": "Dropbox", "date": "2012-07"}]}'
LC_NOT_FOUND = '{"success": true, "found": 0, "sources": []}'


def _mock_json_response(json_text, status_code=200):
    """Create a mock response with .json() and .text."""
    import json
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json.loads(json_text)
    resp.text = json_text
    resp.raise_for_status = Mock()
    return resp


def _route_mock(xon_resp, lc_resp):
    """Return a side_effect function that routes by URL."""
    def side_effect(url, **kwargs):
        if "xposedornot.com" in url:
            if isinstance(xon_resp, Exception):
                raise xon_resp
            return xon_resp
        if "leakcheck.io" in url:
            if isinstance(lc_resp, Exception):
                raise lc_resp
            return lc_resp
        raise ValueError(f"Unexpected URL: {url}")
    return side_effect


class TestCheckEmailBreach:
    @patch("passguard.requests.get")
    def test_both_find_breaches_merged(self, mock_get):
        mock_get.side_effect = _route_mock(
            _mock_json_response(XON_FOUND),
            _mock_json_response(LC_FOUND),
        )
        result = check_email_breach("user@example.com")
        assert result["exposed"] is True
        names = {b["name"].lower() for b in result["breaches"]}
        assert "adobe" in names
        assert "linkedin" in names
        assert "dropbox" in names
        assert len(result["errors"]) == 0
        assert "XposedOrNot" in result["sources_checked"]
        assert "LeakCheck" in result["sources_checked"]

    @patch("passguard.requests.get")
    def test_dedup_prefers_leakcheck(self, mock_get):
        """Adobe appears in both; LeakCheck version (with date) should win."""
        mock_get.side_effect = _route_mock(
            _mock_json_response(XON_FOUND),
            _mock_json_response(LC_FOUND),
        )
        result = check_email_breach("user@example.com")
        adobe = [b for b in result["breaches"] if b["name"].lower() == "adobe"][0]
        assert adobe["source"] == "LeakCheck"
        assert adobe["date"] == "2013-10"

    @patch("passguard.requests.get")
    def test_xon_fails_lc_succeeds(self, mock_get):
        mock_get.side_effect = _route_mock(
            ConnectionError("XON down"),
            _mock_json_response(LC_FOUND),
        )
        result = check_email_breach("user@example.com")
        assert result["exposed"] is True
        assert len(result["errors"]) == 1
        assert "XposedOrNot" in result["errors"][0]
        assert "LeakCheck" in result["sources_checked"]
        assert "XposedOrNot" not in result["sources_checked"]

    @patch("passguard.requests.get")
    def test_lc_fails_xon_succeeds(self, mock_get):
        mock_get.side_effect = _route_mock(
            _mock_json_response(XON_FOUND),
            ConnectionError("LC down"),
        )
        result = check_email_breach("user@example.com")
        assert result["exposed"] is True
        assert len(result["errors"]) == 1
        assert "LeakCheck" in result["errors"][0]
        assert "XposedOrNot" in result["sources_checked"]

    @patch("passguard.requests.get")
    def test_both_fail(self, mock_get):
        mock_get.side_effect = _route_mock(
            ConnectionError("XON down"),
            ConnectionError("LC down"),
        )
        result = check_email_breach("user@example.com")
        assert result["exposed"] is False
        assert len(result["breaches"]) == 0
        assert len(result["errors"]) == 2

    @patch("passguard.requests.get")
    def test_not_found_in_either(self, mock_get):
        mock_get.side_effect = _route_mock(
            _mock_json_response(XON_NOT_FOUND, status_code=404),
            _mock_json_response(LC_NOT_FOUND),
        )
        result = check_email_breach("user@example.com")
        assert result["exposed"] is False
        assert len(result["breaches"]) == 0
        assert len(result["errors"]) == 0
        assert len(result["sources_checked"]) == 2

    def test_invalid_email(self):
        result = check_email_breach("not-an-email")
        assert result["exposed"] is False
        assert len(result["errors"]) == 1
        assert "Invalid" in result["errors"][0]
        assert len(result["sources_checked"]) == 0

    @patch("passguard.requests.get")
    def test_dedup_case_insensitive(self, mock_get):
        """Breach names differing only in case should be deduplicated."""
        xon_data = '{"breaches": [["ADOBE", "linkedin"]]}'
        lc_data = '{"success": true, "found": 1, "sources": [{"name": "adobe", "date": "2013-10"}]}'
        mock_get.side_effect = _route_mock(
            _mock_json_response(xon_data),
            _mock_json_response(lc_data),
        )
        result = check_email_breach("user@example.com")
        adobe_entries = [b for b in result["breaches"] if b["name"].lower() == "adobe"]
        assert len(adobe_entries) == 1
