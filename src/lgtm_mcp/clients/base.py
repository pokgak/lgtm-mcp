"""Base HTTP client with auth, error handling, and connection pooling."""

from typing import Any, Self

import httpx

from lgtm_mcp.models.config import BackendConfig, Settings


class LGTMError(Exception):
    """Base exception for LGTM MCP errors."""

    pass


class AuthenticationError(LGTMError):
    """Authentication failed."""

    pass


class RateLimitError(LGTMError):
    """Rate limited by backend."""

    pass


class APIError(LGTMError):
    """Generic API error."""

    def __init__(
        self, message: str, status_code: int | None = None, response_body: str | None = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class BaseClient:
    """Base HTTP client with common functionality for all backends."""

    def __init__(
        self,
        config: BackendConfig,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.config = config
        self.settings = settings or Settings()
        self._client = http_client
        self._owns_client = http_client is None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> httpx.AsyncClient:
        """Create a new HTTP client with configured settings."""
        headers = dict(self.config.headers)
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"

        return httpx.AsyncClient(
            base_url=self.config.url,
            headers=headers,
            timeout=httpx.Timeout(self.config.timeout),
            limits=httpx.Limits(
                max_connections=self.settings.max_connections,
                max_keepalive_connections=self.settings.max_keepalive_connections,
                keepalive_expiry=self.settings.keepalive_expiry,
            ),
        )

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute GET request with error handling."""
        response = await self.client.get(path, params=self._clean_params(params))
        self._handle_response(response)
        return response.json()

    async def _post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute POST request with error handling."""
        response = await self.client.post(
            path,
            data=data,
            params=self._clean_params(params),
            json=json_body,
        )
        self._handle_response(response)
        return response.json()

    def _clean_params(self, params: dict[str, Any] | None) -> dict[str, Any] | None:
        """Remove None values from params dict."""
        if params is None:
            return None
        return {k: v for k, v in params.items() if v is not None}

    def _handle_response(self, response: httpx.Response) -> None:
        """Handle HTTP errors consistently."""
        if response.status_code == 401:
            raise AuthenticationError(f"Authentication failed for {self.config.url}")
        elif response.status_code == 403:
            raise AuthenticationError(f"Access forbidden for {self.config.url}")
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            msg = f"Rate limited by {self.config.url}"
            if retry_after:
                msg += f" (retry after {retry_after}s)"
            raise RateLimitError(msg)
        elif response.status_code >= 400:
            raise APIError(
                f"API error {response.status_code}: {response.text[:500]}",
                status_code=response.status_code,
                response_body=response.text,
            )

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._client and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
