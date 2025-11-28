"""Shared pytest fixtures for LinguaLeo client tests."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from lingualeo.client import LinguaLeoClient


@pytest.fixture
def mock_cookie_file(tmp_path: Path) -> Path:
    """Create a temporary cookie file path."""
    return tmp_path / "test_cookies.json"


@pytest.fixture
def sample_cookies() -> dict[str, str]:
    """Sample cookie data for testing."""
    return {
        "auth_token": "mock_auth_token_12345",
        "session_id": "mock_session_abc123",
    }


@pytest.fixture
def cookie_file_with_data(tmp_path: Path, sample_cookies: dict[str, str]) -> Path:
    """Create a temporary cookie file with sample data."""
    cookie_file = tmp_path / "test_cookies.json"
    cookie_file.write_text(json.dumps(sample_cookies, indent=2), encoding="utf-8")
    return cookie_file


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.cookies = MagicMock()
    client.cookies.get = MagicMock(return_value="mock_cookie_value")
    client.cookies.items = MagicMock(return_value=[])
    client.cookies.clear = MagicMock()
    client.cookies.update = MagicMock()
    return client


@pytest.fixture
def mock_httpx_response():
    """Create a factory for mock httpx.Response objects."""

    def _create_response(
        status_code: int = 200,
        json_data: dict | None = None,
        cookies: dict[str, str] | None = None,
    ) -> httpx.Response:
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value=json_data or {})
        response.text = json.dumps(json_data) if json_data else ""
        response.cookies = MagicMock()
        if cookies:
            response.cookies = cookies
        return response

    return _create_response


@pytest.fixture
def client_credentials() -> dict[str, str]:
    """Test credentials for client initialization."""
    return {
        "email": "test@example.com",
        "password": "test_password_123",
    }


@pytest.fixture
async def client_with_mock_httpx(
    client_credentials: dict[str, str],
    mock_httpx_client: AsyncMock,
    mock_httpx_response,
    mock_cookie_file: Path,
) -> LinguaLeoClient:
    """Create a LinguaLeoClient with mocked httpx client."""
    client = LinguaLeoClient(
        email=client_credentials["email"],
        password=client_credentials["password"],
        cookie_file=mock_cookie_file,
    )

    # Replace the client's httpx.AsyncClient with our mock
    client.client = mock_httpx_client

    return client


@pytest.fixture
def mock_time(monkeypatch):
    """Mock time.time() to return a fixed timestamp."""
    fixed_time = 1234567890.0

    def mock_time_func():
        return fixed_time

    monkeypatch.setattr("time.time", mock_time_func)
    return fixed_time
