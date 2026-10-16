from datetime import date

import pytest
from pydantic import ValidationError

from deepresearch_app.backends.gptr import GPTRBackend
from deepresearch_app.models import ResearchRequest
from deepresearch_app.network import validate_public_url
from deepresearch_app.settings import Settings


def test_request_rejects_rounds_above_three():
    with pytest.raises(ValidationError):
        ResearchRequest(topic="混合检索", as_of=date(2026, 10, 14), max_rounds=4)


@pytest.mark.parametrize("topic", ["", "   ", "x" * 2001])
def test_invalid_topic_rejected(topic):
    with pytest.raises(ValidationError):
        ResearchRequest(topic=topic)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://localhost/a", "http://127.0.0.1/a", "http://10.0.0.1", "https://user:secret@example.com", "http://[::1]/"])
def test_private_or_credential_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_public_url(url, resolve=False)


def test_live_requires_configuration():
    with pytest.raises(ValueError, match="配置"):
        Settings(mode="live").validate_live()


class FakeSDK:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.scraper = None

    async def conduct_research(self):
        return ["正文摘要", "第二段"]

    async def write_report(self):
        return "基础报告"

    def get_research_sources(self):
        return [
            {"url": "https://example.com/paper?utm_source=test", "title": "资料", "raw_content": "This is source text."},
            {"url": "https://example.com/empty", "title": "无正文", "raw_content": ""},
        ]

    def get_costs(self):
        return 0.125


async def test_unread_sources_are_not_evidence(tmp_path):
    backend = GPTRBackend(Settings(), sdk_factory=FakeSDK, config_dir=tmp_path)
    packet = await backend.research("研究", ResearchRequest(topic="研究"))
    assert len(packet.sources) == 1
    assert packet.sources[0].url == "https://example.com/paper"
    assert packet.context == "正文摘要\n第二段"
    assert packet.usage["cost_complete"] is False
    assert packet.usage["sdk_estimated_usd"] == 0.125


async def test_baseline_uses_sdk_report(tmp_path):
    backend = GPTRBackend(Settings(), sdk_factory=FakeSDK, config_dir=tmp_path)
    text, packet = await backend.baseline(ResearchRequest(topic="研究"))
    assert text == "基础报告"
    assert len(packet.sources) == 1


async def test_every_sdk_query_keeps_constraints_and_cutoff(tmp_path, research_request):
    queries = []
    class InspectSDK(FakeSDK):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            queries.append(kwargs["query"])
    backend = GPTRBackend(Settings(), sdk_factory=InspectSDK, config_dir=tmp_path)
    await backend.research("补搜重排方案", research_request)
    await backend.baseline(research_request)
    assert len(queries) == 2
    for query in queries:
        assert research_request.topic in query
        assert "预算" in query and "有限" in query
        assert research_request.as_of.isoformat() in query
        assert "官方文档" in query and "论文" in query
    assert "补搜重排方案" in queries[0]
