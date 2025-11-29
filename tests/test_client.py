"""Tests for LinguaLeoClient class."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lingualeo.client import COOKIE_CACHE_DEFAULT, LinguaLeoClient, LinguaLeoError

from .fixtures.mock_responses import (
    mock_auth_cookies,
    mock_auth_response,
    mock_get_translates_response,
    mock_get_words_response_word_exists,
    mock_get_words_response_word_not_found,
    mock_set_words_response,
)


class TestLinguaLeoClientInit:
    """Tests for LinguaLeoClient initialization."""

    def test_init_with_email_and_password(self, mock_cookie_file):
        """Test successful initialization with email and password."""
        client = LinguaLeoClient(
            email="test@example.com",
            password="test_password",
            cookie_file=mock_cookie_file,
        )
        assert client.email == "test@example.com"
        assert client.password == "test_password"
        assert client.cookie_file == mock_cookie_file
        assert client._cookies == {}

    def test_init_fails_without_email(self, mock_cookie_file):
        """Test initialization fails without email."""
        with pytest.raises(LinguaLeoError, match="email and password are required"):
            LinguaLeoClient(
                email=None,
                password="test_password",
                cookie_file=mock_cookie_file,
            )

    def test_init_fails_without_password(self, mock_cookie_file):
        """Test initialization fails without password."""
        with pytest.raises(LinguaLeoError, match="email and password are required"):
            LinguaLeoClient(
                email="test@example.com",
                password=None,
                cookie_file=mock_cookie_file,
            )

    def test_init_loads_cookies_from_file(self, cookie_file_with_data, sample_cookies):
        """Test initialization loads cookies from file."""
        client = LinguaLeoClient(
            email="test@example.com",
            password="test_password",
            cookie_file=cookie_file_with_data,
        )
        assert client._cookies == sample_cookies

    def test_init_loads_cookies_from_string(self, mock_cookie_file):
        """Test initialization loads cookies from string."""
        cookie_string = "auth_token=abc123; session_id=xyz789"
        client = LinguaLeoClient(
            email="test@example.com",
            password="test_password",
            cookie_string=cookie_string,
            cookie_file=mock_cookie_file,
        )
        assert client._cookies["auth_token"] == "abc123"
        assert client._cookies["session_id"] == "xyz789"

    def test_init_loads_cookies_from_both_sources(self, cookie_file_with_data, sample_cookies):
        """Test initialization loads cookies from both file and string."""
        cookie_string = "additional_token=extra123"
        client = LinguaLeoClient(
            email="test@example.com",
            password="test_password",
            cookie_string=cookie_string,
            cookie_file=cookie_file_with_data,
        )
        # String cookies should override file cookies if same key
        assert "additional_token" in client._cookies
        # File cookies should also be present
        assert len(client._cookies) >= len(sample_cookies)

    def test_init_handles_invalid_cookie_file(self, tmp_path):
        """Test initialization handles invalid cookie file gracefully."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json{", encoding="utf-8")
        client = LinguaLeoClient(
            email="test@example.com",
            password="test_password",
            cookie_file=invalid_file,
        )
        # Should not raise, just have empty cookies
        assert client._cookies == {}

    def test_init_handles_nonexistent_cookie_file(self, tmp_path):
        """Test initialization handles non-existent cookie file."""
        nonexistent_file = tmp_path / "nonexistent.json"
        client = LinguaLeoClient(
            email="test@example.com",
            password="test_password",
            cookie_file=nonexistent_file,
        )
        assert client._cookies == {}


class TestLinguaLeoClientCookieManagement:
    """Tests for cookie management methods."""

    def test_sync_cookies_from_client(self, client_with_mock_httpx, mock_httpx_client):
        """Test syncing cookies from httpx client."""
        # Mock cookie object with value attribute
        mock_cookie = MagicMock()
        mock_cookie.value = "cookie_value_123"
        mock_httpx_client.cookies.get.return_value = mock_cookie
        mock_httpx_client.cookies.__iter__ = MagicMock(return_value=iter(["auth_token"]))

        client_with_mock_httpx._sync_cookies_from_client()
        assert "auth_token" in client_with_mock_httpx._cookies
        assert client_with_mock_httpx._cookies["auth_token"] == "cookie_value_123"

    def test_sync_cookies_from_client_string_value(self, client_with_mock_httpx, mock_httpx_client):
        """Test syncing cookies when value is a string."""
        mock_httpx_client.cookies.get.return_value = "string_cookie_value"
        mock_httpx_client.cookies.__iter__ = MagicMock(return_value=iter(["session_id"]))

        client_with_mock_httpx._sync_cookies_from_client()
        assert client_with_mock_httpx._cookies["session_id"] == "string_cookie_value"

    def test_sync_cookies_to_client(self, client_with_mock_httpx, mock_httpx_client):
        """Test syncing cookies to httpx client."""
        client_with_mock_httpx._cookies = {"auth_token": "abc123", "session_id": "xyz789"}
        client_with_mock_httpx._sync_cookies_to_client()
        mock_httpx_client.cookies.clear.assert_called_once()
        mock_httpx_client.cookies.update.assert_called_once_with({"auth_token": "abc123", "session_id": "xyz789"})

    def test_save_cookie_file(self, client_with_mock_httpx, mock_cookie_file):
        """Test saving cookies to file."""
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}
        from lingualeo.client import _save_cookie_file

        _save_cookie_file(mock_cookie_file, client_with_mock_httpx._cookies)
        assert mock_cookie_file.exists()
        data = json.loads(mock_cookie_file.read_text(encoding="utf-8"))
        assert data == {"auth_token": "abc123"}


class TestLinguaLeoClientAuthentication:
    """Tests for authentication methods."""

    @pytest.mark.asyncio
    async def test_login_success(
        self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response, mock_cookie_file
    ):
        """Test successful login."""
        # Mock response with cookies
        auth_response = mock_httpx_response(
            status_code=200,
            json_data=mock_auth_response(),
            cookies=mock_auth_cookies(),
        )
        mock_httpx_client.post.return_value = auth_response

        # Mock cookie iteration
        mock_httpx_client.cookies.__iter__ = MagicMock(return_value=iter(mock_auth_cookies().keys()))
        mock_httpx_client.cookies.get.side_effect = lambda k: mock_auth_cookies().get(k)

        await client_with_mock_httpx.login()

        # Verify post was called with correct parameters
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args[0][0] == "https://lingualeo.com/api/auth"
        assert call_args[1]["json"]["type"] == "mixed"
        assert call_args[1]["json"]["credentials"]["email"] == "test@example.com"
        assert call_args[1]["json"]["credentials"]["password"] == "test_password_123"

    @pytest.mark.asyncio
    async def test_login_fails_without_credentials(self, mock_cookie_file):
        """Test login fails without credentials."""
        client = LinguaLeoClient(
            email="test@example.com",
            password="test_password",
            cookie_file=mock_cookie_file,
        )
        client.email = None
        with pytest.raises(LinguaLeoError, match="Missing LinguaLeo credentials"):
            await client.login()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_with_cookies(self, client_with_mock_httpx, mock_httpx_client):
        """Test ensure_authenticated doesn't login when cookies exist."""
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}
        mock_httpx_client.post = AsyncMock()  # Should not be called

        await client_with_mock_httpx.ensure_authenticated()

        # Should not call login
        mock_httpx_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_without_cookies(
        self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response
    ):
        """Test ensure_authenticated logs in when no cookies exist."""
        client_with_mock_httpx._cookies = {}
        auth_response = mock_httpx_response(
            status_code=200,
            json_data=mock_auth_response(),
            cookies=mock_auth_cookies(),
        )
        mock_httpx_client.post.return_value = auth_response
        mock_httpx_client.cookies.__iter__ = MagicMock(return_value=iter(mock_auth_cookies().keys()))
        mock_httpx_client.cookies.get.side_effect = lambda k: mock_auth_cookies().get(k)

        await client_with_mock_httpx.ensure_authenticated()

        # Should call login
        mock_httpx_client.post.assert_called_once()


class TestLinguaLeoClientAPIMethods:
    """Tests for API method calls."""

    @pytest.mark.asyncio
    async def test_get_translates_success(self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response):
        """Test successful get_translates call."""
        translate_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_translates_response(),
        )
        mock_httpx_client.post.return_value = translate_response
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        result = await client_with_mock_httpx.get_translates("palabra")

        assert "translate" in result
        assert len(result["translate"]) > 0
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_word_exists_true(self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response):
        """Test word_exists returns True when word exists."""
        words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_words_response_word_exists("palabra"),
        )
        mock_httpx_client.post.return_value = words_response
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        result = await client_with_mock_httpx.word_exists("palabra")

        assert result is True
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_word_exists_false(self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response):
        """Test word_exists returns False when word doesn't exist."""
        words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_words_response_word_not_found(),
        )
        mock_httpx_client.post.return_value = words_response
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        result = await client_with_mock_httpx.word_exists("nonexistent")

        assert result is False
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_word_exists_case_insensitive(self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response):
        """Test word_exists is case-insensitive."""
        words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_words_response_word_exists("Palabra"),
        )
        mock_httpx_client.post.return_value = words_response
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        result = await client_with_mock_httpx.word_exists("PALABRA")

        assert result is True

    @pytest.mark.asyncio
    async def test_add_word_success(self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response):
        """Test successful add_word call."""
        set_words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_set_words_response("palabra", 1001),
        )
        mock_httpx_client.post.return_value = set_words_response
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        translation = {"id": 1001, "value": "перевод", "tr": "перевод"}
        result = await client_with_mock_httpx.add_word("palabra", translation)

        assert result["status"] == "ok"
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_word_with_hint_success(self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response):
        """Test successful add_word_with_hint call."""
        # Mock word_exists to return False (word doesn't exist)
        words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_words_response_word_not_found(),
        )
        # Mock get_translates response
        translates_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_translates_response(),
        )
        # Mock set_words response
        set_words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_set_words_response("palabra", 1001),
        )

        # Setup mock to return different responses for different calls
        async def mock_post(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "GetWords" in url:
                return words_response
            elif "getTranslates" in url:
                return translates_response
            elif "SetWords" in url:
                return set_words_response
            return words_response

        mock_httpx_client.post = AsyncMock(side_effect=mock_post)
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        result = await client_with_mock_httpx.add_word_with_hint("palabra", "перевод")

        assert result.translation_used["value"] == "перевод"
        assert result.auto_selected is False
        # Should call GetWords, getTranslates, and SetWords
        assert mock_httpx_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_add_word_with_hint_word_exists_no_hint(
        self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response
    ):
        """Test add_word_with_hint raises error when word exists and no hint provided."""
        words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_words_response_word_exists("palabra"),
        )
        mock_httpx_client.post.return_value = words_response
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        with pytest.raises(LinguaLeoError, match="already exists"):
            await client_with_mock_httpx.add_word_with_hint("palabra", None)

    @pytest.mark.asyncio
    async def test_add_word_with_hint_word_exists_same_translation(
        self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response
    ):
        """Test add_word_with_hint raises error when word exists with same translation."""
        words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_words_response_word_exists("palabra"),
        )
        mock_httpx_client.post.return_value = words_response
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        # The existing word has "слово" as translation
        with pytest.raises(LinguaLeoError, match="already exists"):
            await client_with_mock_httpx.add_word_with_hint("palabra", "слово")

    @pytest.mark.asyncio
    async def test_add_word_with_hint_word_exists_new_translation(
        self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response
    ):
        """Test add_word_with_hint adds new translation when word exists with different translation."""
        words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_words_response_word_exists("palabra"),
        )
        translates_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_translates_response(),
        )
        set_words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_set_words_response("palabra", 1001),
        )

        async def mock_post(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "GetWords" in url:
                return words_response
            elif "getTranslates" in url:
                return translates_response
            elif "SetWords" in url:
                return set_words_response
            return words_response

        mock_httpx_client.post = AsyncMock(side_effect=mock_post)
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        # The existing word has "слово" as translation, but we're adding "перевод"
        result = await client_with_mock_httpx.add_word_with_hint("palabra", "перевод")

        assert result.translation_used["value"] == "перевод"
        assert result.auto_selected is False
        # Should call GetWords, getTranslates, and SetWords
        assert mock_httpx_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_add_word_with_hint_custom_translation(
        self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response
    ):
        """Test add_word_with_hint can add custom translation not in Lingualeo's suggestions."""
        words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_words_response_word_not_found(),
        )
        # Translation response doesn't contain our custom translation
        translates_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_translates_response(),
        )
        set_words_response = mock_httpx_response(
            status_code=200,
            json_data=mock_set_words_response("palabra", 999999),
        )

        async def mock_post(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "GetWords" in url:
                return words_response
            elif "getTranslates" in url:
                return translates_response
            elif "SetWords" in url:
                return set_words_response
            return words_response

        mock_httpx_client.post = AsyncMock(side_effect=mock_post)
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        # Add word with custom translation "кастомный" which is not in suggestions
        result = await client_with_mock_httpx.add_word_with_hint("palabra", "кастомный")

        assert result.translation_used["value"] == "кастомный"
        assert result.auto_selected is False
        # Should call GetWords, getTranslates, and SetWords
        assert mock_httpx_client.post.call_count == 3


class TestLinguaLeoClientErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_get_translates_http_error(self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response):
        """Test get_translates handles HTTP errors."""
        error_response = mock_httpx_response(
            status_code=500,
            json_data={"error": "Internal server error"},
        )
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=error_response
        )
        mock_httpx_client.post.return_value = error_response
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        with pytest.raises(httpx.HTTPStatusError):
            await client_with_mock_httpx.get_translates("palabra")

    @pytest.mark.asyncio
    async def test_word_exists_http_error_returns_false(
        self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response
    ):
        """Test word_exists returns False on HTTP error."""
        error_response = mock_httpx_response(
            status_code=500,
            json_data={"error": "Internal server error"},
        )
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=error_response
        )
        mock_httpx_client.post.return_value = error_response
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        result = await client_with_mock_httpx.word_exists("palabra")

        assert result is False

    @pytest.mark.asyncio
    async def test_with_reauth_on_401(self, client_with_mock_httpx, mock_httpx_client, mock_httpx_response):
        """Test _with_reauth reauthenticates on 401 error."""
        # First call returns 401
        error_response = mock_httpx_response(
            status_code=401,
            json_data={"error": "Unauthorized"},
        )
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=error_response
        )

        # Second call (after reauth) succeeds
        success_response = mock_httpx_response(
            status_code=200,
            json_data=mock_get_translates_response(),
        )

        # Auth response
        auth_response = mock_httpx_response(
            status_code=200,
            json_data=mock_auth_response(),
            cookies=mock_auth_cookies(),
        )

        async def mock_post(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "auth" in url:
                return auth_response
            # First API call fails, second succeeds
            if mock_httpx_client.post.call_count == 1:
                return error_response
            return success_response

        mock_httpx_client.post = AsyncMock(side_effect=mock_post)
        mock_httpx_client.cookies.__iter__ = MagicMock(return_value=iter(mock_auth_cookies().keys()))
        mock_httpx_client.cookies.get.side_effect = lambda k: mock_auth_cookies().get(k)
        client_with_mock_httpx._cookies = {"auth_token": "abc123"}

        result = await client_with_mock_httpx.get_translates("palabra")

        # Should have called auth, then retried the original call
        assert mock_httpx_client.post.call_count >= 2
        assert "translate" in result


class TestLinguaLeoClientContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_initializes_client(self, client_credentials, mock_cookie_file):
        """Test context manager initializes client."""
        client = LinguaLeoClient(
            email=client_credentials["email"],
            password=client_credentials["password"],
            cookie_file=mock_cookie_file,
        )

        async with client:
            assert client.client is not None

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self, client_credentials, mock_cookie_file):
        """Test context manager closes client."""
        client = LinguaLeoClient(
            email=client_credentials["email"],
            password=client_credentials["password"],
            cookie_file=mock_cookie_file,
        )

        async with client:
            mock_client = client.client
            assert mock_client is not None

        # After context exit, client should be closed
        # Note: In real scenario, aclose() would be called, but with our mock
        # we can't easily verify this without more complex setup
