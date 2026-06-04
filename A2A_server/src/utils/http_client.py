import httpx
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

logger = logging.getLogger(__file__)

# Retry on transient errors: 5xx responses, timeouts, connection errors
_RETRYABLE_STATUS_CODES = {502, 503, 504, 429}

def _is_retryable(exc: BaseException) -> bool:
    """ Determine if an exception is transient """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout)):
        return True
    return False

class HTTPClient:
    """ Reusable async HTTP client with shared connection pool & retry logic.
        Call ``HTTPClient.start()`` during application startup &
        ``HTTPClient.stop()`` at shutdown.

        Retries transient failure upto 3 attempts with exponential backoff (1s, 2s, 3s).
    """

    _client: httpx.AsyncClient | None = None

    @classmethod
    def start(cls, timeout: float = 30.0) -> None:
        """ Create a shared AsyncClient at startup """
        if cls._client is None:
            cls._client = httpx.AsyncClient(timeout=timeout)
            logger.info("HTTPClient started")

    @classmethod
    async def stop(cls) -> None:
        """ close shared AsyncClient at app shutdown """
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None
            logger.info("HTTPClient stopped")

    @classmethod
    def _get_client(cls) -> httpx.AsyncClient:
        if cls._client is None:
            raise RuntimeError("HTTPClient not started. Call HTTPClient.start() durnig app lifespan")
        return cls._client
    
    @classmethod
    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def call_api(
        cls,
        url: str,
        *,
        method: str,
        payload: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        content_type: str | None = None,
        timeout: float = 30.0
    ) -> dict:
        try:
            client = cls._get_client()
            if headers is None:
                headers = {}
            headers["Content-Type"] = content_type
            request: dict = {"headers": headers, "timeout": timeout}
            if params is not None:
                request["params"] = params
            if payload is not None:
                request["json"] = payload

            # `**request` unpack this dictionary into keyword arguments as 
            # client.request(
            #        method,
            #        url,
            #        headers={"Content-Type": "application/json"},
            #        timeout=30.0,
            #        params={"page": 1},
            #        json={"name": "Alice"}
            #        )
            
            response = await client.request(method, url, **request)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}", ex=e)
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error : {str(e)}", ex=e)
            raise
        except Exception as e:
            logger.error(f"Unexpected HTTP error : {str(e)}", ex=e)
            raise
