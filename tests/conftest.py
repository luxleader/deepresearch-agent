from datetime import date

import pytest

from deepresearch_app.models import Evidence, ResearchRequest, Source


@pytest.fixture
def research_request():
    return ResearchRequest(topic="选择检索方案", constraints={"预算": "有限"}, as_of=date(2026, 10, 14))


@pytest.fixture
def sources():
    return [Source(id="s1", url="https://example.org/synthetic", title="人工构造来源",
                   text="Vector retrieval uses embeddings. Hybrid retrieval combines keyword and vector search.",
                   content_hash="fixture", published_at=date(2026, 1, 1), time_status="within_cutoff",
                   source_type="synthetic")]


@pytest.fixture
def evidence():
    return [Evidence(id="e1", source_id="s1", quote="Vector retrieval uses embeddings.",
                     claim="向量检索使用嵌入表示。", verdict="supported", reason="人工构造测试标签")]
