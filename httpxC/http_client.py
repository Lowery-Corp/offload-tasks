from httpx import AsyncClient, Limits, Timeout

http_client = AsyncClient(
    timeout=Timeout(connect=2.0, read=5.0, write=5.0, pool=5.0),
    limits=Limits(max_connections=100, max_keepalive_connections=20),
)