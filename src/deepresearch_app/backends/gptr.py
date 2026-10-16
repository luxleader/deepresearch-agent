import hashlib
import json
import tempfile
import time
from datetime import date
from pathlib import Path

from ..models import ResearchPacket, Source
from ..network import SafeBrowser, canonical_url

UPSTREAM_COMMIT = "3582a6841fe7dc801e2a34e34ee408641aea9bce"


def research_query(question, request):
    scope = {"研究主题": request.topic, "本次子问题": question, "使用约束": request.constraints,
             "资料截止日期": request.as_of.isoformat()}
    return ("根据以下研究范围检索官方文档与论文，围绕使用约束取材。优先原始来源，保留版本和实验条件。"
            "晚于截止日期的资料不作为当时事实；无法确认日期时明确未知。\n"
            + json.dumps(scope, ensure_ascii=False))


def normalize_sources(raw_sources, request):
    sources = {}
    for raw in raw_sources:
        text = raw.get("raw_content") or raw.get("content") or raw.get("text") or ""
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            url = canonical_url(raw.get("url") or raw.get("href") or "")
        except ValueError:
            continue
        digest = hashlib.sha256(text.encode()).hexdigest()
        sid = "s-" + hashlib.sha256((url + digest).encode()).hexdigest()[:16]
        try:
            published = date.fromisoformat(str(raw.get("published_at", ""))[:10])
        except ValueError:
            published = None
        status = "unknown" if published is None else "after_cutoff" if published > request.as_of else "within_cutoff"
        sources[sid] = Source(id=sid, url=url, title=str(raw.get("title", url)), text=text,
                             content_hash=digest, published_at=published, time_status=status,
                             source_type=raw.get("source_type", "unknown"), version=raw.get("version"))
    return list(sources.values())


class GPTRBackend:
    mode = "live"

    def __init__(self, settings, *, sdk_factory=None, config_dir=None):
        self.settings = settings
        self.sdk_factory = sdk_factory
        self.config_dir = Path(config_dir or "runtime/sdk-config")

    def _new_sdk(self, question):
        factory = self.sdk_factory
        if factory is None:
            self.settings.validate_live()
            try:
                from gpt_researcher import GPTResearcher
            except ImportError as exc:
                raise RuntimeError("请先安装 requirements-live.txt 中固定版本的 GPT Researcher") from exc
            factory = GPTResearcher
        self.config_dir.mkdir(parents=True, exist_ok=True)
        config = {"LANGUAGE": "chinese", "MAX_ITERATIONS": 2, "MAX_SEARCH_RESULTS_PER_QUERY": 4,
                  "MAX_SCRAPER_WORKERS": 2, "DEEP_RESEARCH_CONCURRENCY": 2,
                  "DEEP_RESEARCH_DEPTH": 2, "DEEP_RESEARCH_BREADTH": 3,
                  "CONTEXT_FILTER": "keyword", "IMAGE_GENERATION_ENABLED": False,
                  "RETRIEVER": "tavily", "FAST_LLM": "openai:" + self.settings.model,
                  "SMART_LLM": "openai:" + self.settings.model, "STRATEGIC_LLM": "openai:" + self.settings.model}
        config["LLM_KWARGS"] = self.settings.llm_kwargs()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=self.config_dir, delete=False, encoding="utf-8") as f:
            json.dump(config, f)
            path = f.name
        try:
            sdk = factory(query=question, config_path=path, verbose=False, report_type="research_report", mcp_strategy="disabled")
        finally:
            Path(path).unlink(missing_ok=True)
        sdk.scraper_manager = SafeBrowser(sdk)
        return sdk

    def _packet(self, sdk, context, request, start):
        return ResearchPacket(context="\n".join(map(str, context)) if isinstance(context, list) else str(context),
                              sources=normalize_sources(sdk.get_research_sources(), request),
                              usage={"sdk_estimated_usd": sdk.get_costs(), "cost_complete": False},
                              duration_ms=int((time.perf_counter() - start) * 1000))

    async def research(self, question, request):
        start = time.perf_counter()
        sdk = self._new_sdk(research_query(question, request))
        context = await sdk.conduct_research()
        return self._packet(sdk, context, request, start)

    async def baseline(self, request):
        start = time.perf_counter()
        query = research_query(request.topic, request)
        sdk = self._new_sdk(query)
        context = await sdk.conduct_research()
        report = await sdk.write_report()
        return report, self._packet(sdk, context, request, start)
