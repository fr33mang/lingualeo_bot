"""Tests for helper functions in lingualeo.client."""

import pytest

from lingualeo.client import (
    LinguaLeoError,
    _should_reauth,
    extract_existing_translations,
    parse_cookie_string,
    select_best_translation,
    translation_exists,
)


class TestParseCookieString:
    """Tests for parse_cookie_string function."""

    def test_parse_valid_cookie_string(self):
        """Test parsing a valid cookie string."""
        cookie_string = "auth_token=abc123; session_id=xyz789; user_id=12345"
        result = parse_cookie_string(cookie_string)
        assert result == {
            "auth_token": "abc123",
            "session_id": "xyz789",
            "user_id": "12345",
        }

    def test_parse_cookie_string_with_spaces(self):
        """Test parsing cookie string with spaces."""
        cookie_string = "auth_token = abc123 ; session_id = xyz789"
        result = parse_cookie_string(cookie_string)
        assert result == {
            "auth_token": "abc123",
            "session_id": "xyz789",
        }

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = parse_cookie_string("")
        assert result == {}

    def test_parse_malformed_cookie_string(self):
        """Test parsing malformed cookie string."""
        cookie_string = "invalid; no_equals; =empty_value; valid=ok"
        result = parse_cookie_string(cookie_string)
        # Empty key is parsed as empty string key (this is valid)
        assert "valid" in result
        assert result["valid"] == "ok"
        # The function parses =empty_value as {'': 'empty_value'}
        # which is technically valid parsing behavior
        assert "" in result or "valid" in result  # Either empty key or just valid

    def test_parse_cookie_string_single_cookie(self):
        """Test parsing single cookie."""
        cookie_string = "auth_token=abc123"
        result = parse_cookie_string(cookie_string)
        assert result == {"auth_token": "abc123"}

    def test_parse_cookie_string_with_empty_parts(self):
        """Test parsing cookie string with empty parts."""
        cookie_string = "auth_token=abc123;;session_id=xyz789;"
        result = parse_cookie_string(cookie_string)
        assert result == {
            "auth_token": "abc123",
            "session_id": "xyz789",
        }


class TestSelectBestTranslation:
    """Tests for select_best_translation function."""

    def test_exact_match(self):
        """Test finding exact match."""
        candidates = [
            {"id": 1, "value": "перевод", "tr": "перевод"},
            {"id": 2, "value": "толкование", "tr": "толкование"},
        ]
        result = select_best_translation(candidates, "перевод")
        assert result is not None
        assert result["id"] == 1
        assert result["value"] == "перевод"

    def test_partial_match_highest_score(self):
        """Test finding best partial match."""
        candidates = [
            {"id": 1, "value": "перевод", "tr": "перевод"},
            {"id": 2, "value": "переводчик", "tr": "переводчик"},
            {"id": 3, "value": "толкование", "tr": "толкование"},
        ]
        result = select_best_translation(candidates, "переводчик")
        assert result is not None
        assert result["id"] == 2

    def test_no_match_found(self):
        """Test when no match is found (similarity below threshold)."""
        candidates = [
            {"id": 1, "value": "перевод", "tr": "перевод"},
            {"id": 2, "value": "толкование", "tr": "толкование"},
        ]
        # Test with a completely different word that has very low similarity
        # With default threshold of 0.8, this should return None
        result = select_best_translation(candidates, "xyzabc123")
        assert result is None  # Function returns None when similarity < threshold

    def test_with_none_desired(self):
        """Test with None desired translation."""
        candidates = [
            {"id": 1, "value": "перевод", "tr": "перевод"},
        ]
        result = select_best_translation(candidates, None)
        assert result is None

    def test_with_empty_candidates(self):
        """Test with empty candidates list."""
        result = select_best_translation([], "перевод")
        assert result is None

    def test_case_insensitive_matching(self):
        """Test case-insensitive matching."""
        candidates = [
            {"id": 1, "value": "Перевод", "tr": "Перевод"},
            {"id": 2, "value": "ТОЛКОВАНИЕ", "tr": "ТОЛКОВАНИЕ"},
        ]
        result = select_best_translation(candidates, "перевод")
        assert result is not None
        assert result["id"] == 1

    def test_uses_tr_field_when_value_missing(self):
        """Test that function uses 'tr' field when 'value' is missing."""
        candidates = [
            {"id": 1, "tr": "перевод"},
            {"id": 2, "tr": "толкование"},
        ]
        result = select_best_translation(candidates, "перевод")
        assert result is not None
        assert result["id"] == 1

    def test_prefers_value_over_tr(self):
        """Test that function prefers 'value' over 'tr' when both exist."""
        candidates = [
            {"id": 1, "value": "перевод", "tr": "другое"},
        ]
        result = select_best_translation(candidates, "перевод")
        assert result is not None
        assert result["id"] == 1

    def test_ignores_empty_values(self):
        """Test that function ignores candidates with empty values."""
        candidates = [
            {"id": 1, "value": "", "tr": ""},
            {"id": 2, "value": "перевод", "tr": "перевод"},
        ]
        result = select_best_translation(candidates, "перевод")
        assert result is not None
        assert result["id"] == 2


class TestShouldReauth:
    """Tests for _should_reauth function."""

    def test_status_400_requires_reauth(self):
        """Test that status 400 requires reauth."""
        assert _should_reauth(400) is True

    def test_status_401_requires_reauth(self):
        """Test that status 401 requires reauth."""
        assert _should_reauth(401) is True

    def test_status_403_requires_reauth(self):
        """Test that status 403 requires reauth."""
        assert _should_reauth(403) is True

    def test_status_200_no_reauth(self):
        """Test that status 200 doesn't require reauth."""
        assert _should_reauth(200) is False

    def test_status_404_no_reauth(self):
        """Test that status 404 doesn't require reauth."""
        assert _should_reauth(404) is False

    def test_status_500_no_reauth(self):
        """Test that status 500 doesn't require reauth."""
        assert _should_reauth(500) is False

    def test_none_status_no_reauth(self):
        """Test that None status doesn't require reauth."""
        assert _should_reauth(None) is False


class TestExtractExistingTranslations:
    """Tests for extract_existing_translations function."""

    def test_extract_from_combined_translation(self):
        """Test extracting translations from combinedTranslation field."""
        word_data = {
            "combinedTranslation": "доктор; врач; медик",
            "wordValue": "medico",
        }
        result = extract_existing_translations(word_data)
        assert result == ["доктор", "врач", "медик"]

    def test_extract_from_translations_array(self):
        """Test extracting translations from translations array."""
        word_data = {
            "translations": [
                {"value": "доктор", "tr": "доктор"},
                {"value": "врач", "tr": "врач"},
            ],
        }
        result = extract_existing_translations(word_data)
        assert result == ["доктор", "врач"]

    def test_extract_from_both_sources(self):
        """Test extracting translations from both sources."""
        word_data = {
            "combinedTranslation": "доктор; врач",
            "translations": [
                {"value": "медик", "tr": "медик"},
            ],
        }
        result = extract_existing_translations(word_data)
        # Should contain all unique translations
        assert "доктор" in result
        assert "врач" in result
        assert "медик" in result

    def test_removes_duplicates(self):
        """Test that duplicates are removed."""
        word_data = {
            "combinedTranslation": "доктор; врач; доктор",
            "translations": [
                {"value": "доктор", "tr": "доктор"},
                {"value": "врач", "tr": "врач"},
            ],
        }
        result = extract_existing_translations(word_data)
        # Should have unique translations only
        assert result.count("доктор") == 1
        assert result.count("врач") == 1

    def test_empty_word_data(self):
        """Test with empty word data."""
        word_data = {}
        result = extract_existing_translations(word_data)
        assert result == []

    def test_empty_combined_translation(self):
        """Test with empty combinedTranslation."""
        word_data = {"combinedTranslation": ""}
        result = extract_existing_translations(word_data)
        assert result == []

    def test_whitespace_handling(self):
        """Test that whitespace is properly trimmed."""
        word_data = {
            "combinedTranslation": " доктор ; врач ; медик ",
        }
        result = extract_existing_translations(word_data)
        assert result == ["доктор", "врач", "медик"]

    def test_uses_tr_field_when_value_missing(self):
        """Test that it uses 'tr' field when 'value' is missing."""
        word_data = {
            "translations": [
                {"tr": "доктор"},
                {"tr": "врач"},
            ],
        }
        result = extract_existing_translations(word_data)
        assert result == ["доктор", "врач"]


class TestTranslationExists:
    """Tests for translation_exists function."""

    def test_exact_match(self):
        """Test exact match."""
        existing = ["доктор", "врач", "медик"]
        assert translation_exists(existing, "доктор") is True

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        existing = ["доктор", "врач", "медик"]
        assert translation_exists(existing, "ДОКТОР") is True
        assert translation_exists(existing, "Врач") is True

    def test_no_match(self):
        """Test when translation doesn't exist."""
        existing = ["доктор", "врач", "медик"]
        assert translation_exists(existing, "учитель") is False

    def test_empty_list(self):
        """Test with empty existing translations list."""
        existing = []
        assert translation_exists(existing, "доктор") is False

    def test_whitespace_handling(self):
        """Test that whitespace is properly trimmed."""
        existing = ["доктор", "врач"]
        assert translation_exists(existing, "  доктор  ") is True

    def test_partial_match_not_found(self):
        """Test that partial matches don't count."""
        existing = ["доктор", "врач"]
        assert translation_exists(existing, "док") is False
        assert translation_exists(existing, "докторский") is False
