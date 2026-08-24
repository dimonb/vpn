"""Tests for main application module."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.main import app


class TestMainApp:
    """Test main application functionality."""

    def test_health_check(self) -> None:
        """Test health check endpoint."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "version": "0.1.0"}

    @pytest.mark.asyncio
    async def test_http_exception_propagation(self) -> None:
        """Test that HTTPException is properly propagated instead of being converted to 500."""
        from src.auth import require_auth

        # Create a mock request that will fail authentication
        request = Mock()
        request.url.query = ""

        # This should raise HTTPException with 401 status
        with pytest.raises(HTTPException) as exc_info:
            require_auth(request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"

    @patch("src.main.forward_request")
    def test_proxy_handler_json_output(self, mock_forward: Mock) -> None:
        """Test proxy handler returns JSON when json=true parameter is provided."""
        import httpx

        # Mocking an httpx.Response for forward_request
        mock_response = httpx.Response(
            status_code=200,
            content=b"proxies:\n  - name: proxy1\n    type: vless",
            request=httpx.Request("GET", "https://example.com/config.yaml"),
        )

        mock_forward.return_value = mock_response

        client = TestClient(app)

        # Request with json=true
        response = client.get("/config.yaml?json=true")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert "proxies" in data
        assert len(data["proxies"]) == 1
        assert data["proxies"][0]["name"] == "proxy1"

    @patch("src.main.forward_request")
    def test_proxy_handler_yaml_output(self, mock_forward: Mock) -> None:
        """Test proxy handler returns YAML when json parameter is missing."""
        import httpx

        mock_response = httpx.Response(
            status_code=200,
            content=b"proxies:\n  - name: proxy1\n    type: vless",
            request=httpx.Request("GET", "https://example.com/config.yaml"),
        )

        mock_forward.return_value = mock_response

        client = TestClient(app)

        # Request without json parameter
        response = client.get("/config.yaml")

        assert response.status_code == 200
        assert "application/json" not in response.headers.get("content-type", "")
        # The content could be unaltered bytes or a re-serialized representation
        assert b"proxies:" in response.content

    @patch("src.main.TemplateProcessor.process_template")
    @patch("src.main.forward_request")
    def test_proxy_handler_list_timeout_returns_504(
        self, mock_forward: Mock, mock_process: Mock
    ) -> None:
        """A list lost to a timeout must fail the request, not serve a partial config."""
        import httpx

        from src.processor import ListFetchError

        url = "https://raw.githubusercontent.com/list.txt"
        mock_forward.side_effect = _origin_404_then_template()
        mock_process.side_effect = ListFetchError(url, httpx.ReadTimeout("timed out"))

        client = TestClient(app)
        response = client.get("/example.conf")

        assert response.status_code == 504
        assert "IP-CIDR" not in response.text

    @patch("src.main.TemplateProcessor.process_template")
    @patch("src.main.forward_request")
    def test_proxy_handler_list_error_returns_502(
        self, mock_forward: Mock, mock_process: Mock
    ) -> None:
        """Any other list failure (e.g. non-success status) returns 502."""
        from src.processor import ListFetchError

        url = "https://raw.githubusercontent.com/list.txt"
        mock_forward.side_effect = _origin_404_then_template()
        mock_process.side_effect = ListFetchError(url, "HTTP 503")

        client = TestClient(app)
        response = client.get("/example.conf")

        assert response.status_code == 502
        assert "IP-CIDR" not in response.text


def _origin_404_then_template() -> list:
    """Origin 404 for the bare path, then a template with one RULE-SET."""
    import httpx

    request = httpx.Request("GET", "https://example.com/example.conf")
    return [
        httpx.Response(status_code=404, content=b"", request=request),
        httpx.Response(
            status_code=200,
            content=b"RULE-SET,https://raw.githubusercontent.com/list.txt,PROXY\n",
            request=request,
        ),
    ]
