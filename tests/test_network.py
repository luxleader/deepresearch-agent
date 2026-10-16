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


@pytest.fixture
def serve_html(monkeypatch):
    real_client = httpx.AsyncClient
    def serve(html):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(
            lambda req: httpx.Response(200, text=html, headers={"content-type": "text/html; charset=utf-8"}))))
    return serve


async def test_html_title_and_explicit_publication_metadata(serve_html):
    serve_html('''<html><head><title>论文 &amp; 文档</title>
      <meta property="article:published_time" content="2026-10-15T12:00:00+08:00">
      <meta property="article:modified_time" content="2026-10-16T08:00:00+08:00">
      <script>ignore me</script></head><body><main>实际研究正文。</main></body></html>''')
    raw = await read_public_document("https://example.org/doc")
    assert raw["title"] == "论文 & 文档"
    assert raw["published_at"] == "2026-10-15"
    assert raw["modified_at"] == "2026-10-16"
    assert raw["date_basis"] == "meta:article:published_time"
    assert "实际研究正文" in raw["raw_content"] and "ignore me" not in raw["raw_content"]


async def test_modified_time_alone_is_not_a_publication_date(serve_html):
    serve_html('<head><meta property="article:modified_time" content="2026-10-16"></head><body>正文</body>')
    raw = await read_public_document("https://example.org/doc")
    assert raw.get("published_at") is None
    assert raw["modified_at"] == "2026-10-16"


async def test_conflicting_publication_dates_stay_unknown(serve_html):
    serve_html('''<head><meta property="article:published_time" content="2026-10-15">
        <meta name="citation_publication_date" content="2025-01-02"></head><body>正文</body>''')
    raw = await read_public_document("https://example.org/doc")
    assert raw.get("published_at") is None
    assert raw["metadata_warnings"]


async def test_jsonld_publication_and_invalid_dates(serve_html):
    serve_html('''<head><title>参考文档</title><meta property="article:published_time" content="2026-02-31">
        <script type="application/ld+json">{"@graph":[{"@type":"TechArticle","datePublished":"2026-10-14","dateModified":"2026-10-16"}]}</script>
        </head><body>页面正文</body>''')
    raw = await read_public_document("https://example.org/doc")
    assert raw["published_at"] == "2026-10-14"
    assert raw["date_basis"] == "jsonld:datePublished"
    assert "datePublished" not in raw["raw_content"]
