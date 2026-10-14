import socket

import httpx
import pytest

from deepresearch_app.network import read_public_document


async def test_dns_rebinding_never_connects_private_ip(monkeypatch):
    lookups = 0
    contacts = []

    def resolve(*args):
        nonlocal lookups
        lookups += 1
        ip = "93.184.216.34" if lookups == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]

    def handler(request):
        contacts.append(request.url.host)
        return httpx.Response(200, text="public text", headers={"content-type": "text/html"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler)))
    try:
        await read_public_document("https://example.org/doc")
    except ValueError:
        pass
    assert all(ip != "127.0.0.1" for ip in contacts)


async def test_private_redirect_is_blocked(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    contacts = []
    def handler(request):
        contacts.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/internal"})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError):
        await read_public_document("https://example.org/doc")
    assert len(contacts) == 1
