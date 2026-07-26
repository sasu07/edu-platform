"""Rate limiting (slowapi) — protecție împotriva brute-force / credential stuffing.

În spatele lui Caddy, `request.client.host` este IP-ul proxy-ului (mereu același),
deci citim IP-ul real al clientului din antetul `X-Forwarded-For` setat de Caddy.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address


def client_ip(request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Primul IP din listă = clientul real
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)
