def client_ip(request):
    """Best-effort client IP for lightweight rate limiting.

    Uses REMOTE_ADDR directly rather than X-Forwarded-For, which a client
    can set to any value it likes - trusting it blindly would make IP-based
    throttling trivially bypassable. Once deployed behind a reverse proxy
    (e.g. Cloudflare), REMOTE_ADDR will show the proxy's own IP rather than
    the visitor's; at that point this needs revisiting to trust a specific
    forwarded-for header, but only when it can be tied to the proxy's own
    connection, not just present in the request.
    """
    return request.META.get("REMOTE_ADDR", "")
