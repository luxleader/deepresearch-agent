import asyncio
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx


def validate_public_url(url: str, *, resolve=True) -> str:
    p = urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("来源必须是无凭据的公开 HTTP/HTTPS URL")
    host = p.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("禁止读取本地来源")
    if p.port not in {None, 80, 443}:
        raise ValueError("来源只允许标准网页端口")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = []
        if resolve:
            addresses = [ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host, p.port or 443)]
    if any(not ip.is_global for ip in addresses):
        raise ValueError("禁止读取私有或保留网络地址")
    return url


def canonical_url(url: str) -> str:
    validate_public_url(url, resolve=False)
    p = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", urlencode(query), ""))


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


async def read_public_document(url: str) -> dict:
    """Pin a validated public DNS address and check every redirect before reading."""
    async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
        for _ in range(6):
            await asyncio.to_thread(validate_public_url, url)
            p = urlsplit(url)
            addresses = await asyncio.to_thread(socket.getaddrinfo, p.hostname, p.port or (443 if p.scheme == "https" else 80))
            address = addresses[0][4][0]
            host = f"[{address}]" if ":" in address else address
            target = urlunsplit((p.scheme, host + (f":{p.port}" if p.port else ""), p.path, p.query, ""))
            async with client.stream("GET", target, headers={"Host": p.netloc}, extensions={"sni_hostname": p.hostname}) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 8_000_000:
                        raise ValueError("来源超过 8MB 读取上限")
                content_type = response.headers.get("content-type", "")
                if "pdf" in content_type or bytes(chunks[:4]) == b"%PDF":
                    import io

                    from pypdf import PdfReader

                    reader = PdfReader(io.BytesIO(chunks))
                    text = "\n".join(page.extract_text() or "" for page in list(reader.pages)[:20])
                else:
                    parser = TextParser()
                    parser.feed(bytes(chunks).decode(response.encoding or "utf-8", errors="replace"))
                    text = "\n".join(parser.parts)
                return {"url": url, "title": p.hostname, "raw_content": text[:100000]}
    raise ValueError("来源重定向次数过多")


class SafeBrowser:
    def __init__(self, researcher):
        self.researcher = researcher
        self.semaphore = asyncio.Semaphore(2)

    async def browse_urls(self, urls):
        async def read(url):
            async with self.semaphore:
                try:
                    return await read_public_document(url)
                except (ValueError, OSError, httpx.HTTPError):
                    return None

        results = [r for r in await asyncio.gather(*(read(u) for u in dict.fromkeys(urls))) if r and r["raw_content"].strip()]
        self.researcher.add_research_sources(results)
        return results
