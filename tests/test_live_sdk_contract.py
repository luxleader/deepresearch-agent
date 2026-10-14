import pytest

from deepresearch_app.backends.gptr import GPTRBackend
from deepresearch_app.network import SafeBrowser
from deepresearch_app.settings import Settings


def test_actual_pinned_sdk_accepts_qwen_config_without_network(tmp_path, monkeypatch):
    pytest.importorskip("gpt_researcher")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-constructor-fixture")
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic-constructor-fixture")
    settings = Settings(provider="qwen", model="qwen-plus", api_key="synthetic-constructor-fixture",
                        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1")
    sdk = GPTRBackend(settings, config_dir=tmp_path)._new_sdk("官方技术文档研究")
    assert sdk.cfg.context_filter == "keyword"
    assert sdk.cfg.llm_kwargs["extra_body"]["enable_thinking"] is False
    assert sdk.cfg.llm_kwargs["openai_api_base"] == settings.api_base
    assert isinstance(sdk.scraper_manager, SafeBrowser)
