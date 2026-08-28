import asyncio

import httpx

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class PoliteClient:
    """Async HTTP client with a per-host request delay and retries."""

    def __init__(self, delay: float = 1.0, timeout: float = 40.0):
        self.delay = delay
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT,
                     "Accept-Language": "mk,en;q=0.8"},
            timeout=timeout,
            follow_redirects=True,
        )

    async def get(self, url: str, retries: int = 3) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(retries):
            async with self._lock:
                if attempt or self.delay:
                    await asyncio.sleep(self.delay * (2 ** attempt if attempt else 1))
                try:
                    resp = await self._client.get(url)
                except httpx.HTTPError as exc:
                    last_exc = exc
                    continue
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
                return resp
            last_exc = httpx.HTTPStatusError(
                f"{resp.status_code} for {url}", request=resp.request, response=resp)
        raise last_exc  # type: ignore[misc]

    async def aclose(self) -> None:
        await self._client.aclose()
