import json
from pathlib import Path

import pytest

from deepresearch_app.backends.replay import ReplayBackend, ReplayModel
from deepresearch_app.evaluation import export_blind_pairs, run_pair, score_claims, validate_splits
from deepresearch_app.models import ReportClaim, ResearchReport
from deepresearch_app.storage import SQLiteStore


def task(id="dev-01", family="retrieval"):
    return {"id": id, "topic_family": family, "topic": "如何选择方案？", "constraints": {"预算": "有限"},
            "as_of": "2026-10-14", "required_dimensions": ["预算", "部署"]}


def test_same_topic_family_cannot_leak_across_splits():
    with pytest.raises(ValueError, match="topic_family"):
        validate_splits([task()], [task("holdout-01")])
    with pytest.raises(ValueError, match="id"):
        validate_splits([task()], [task(family="inference")])


def test_zero_claims_and_missing_labels_not_reported_as_scores():
    empty = ResearchReport(title="empty", claims=[], summary_claim_ids=[])
    assert score_claims(empty, {})["citation_support_rate"] is None
    report = empty.model_copy(update={"claims": [ReportClaim(id="c1", text="命题", kind="fact")]})
    assert score_claims(report, {})["unsupported_claim_rate"] is None
    assert score_claims(report, {"claims": {"c1": {"citation_supported": True, "fact_supported": True}}})["citation_support_rate"] is None


def test_human_labels_have_explicit_denominators():
    report = ResearchReport(title="x", summary_claim_ids=["a"], claims=[
        ReportClaim(id="a", text="甲", kind="fact", evidence_ids=["e1"]),
        ReportClaim(id="b", text="乙", kind="fact", evidence_ids=["e2"]),
        ReportClaim(id="r", text="建议", kind="recommendation")])
    labels = {"claims": {"a": {"citation_supported": True, "fact_supported": True},
                         "b": {"citation_supported": False, "fact_supported": False}},
              "required_dimensions": ["成本", "部署"], "covered_dimensions": ["部署"], "blind_score": 4}
    metrics = score_claims(report, labels)
    assert metrics["citation_support_rate"] == 0.5
    assert metrics["unsupported_claim_rate"] == 0.5
    assert metrics["dimension_coverage"] == 0.5
    assert metrics["blind_score"] == 4
    assert score_claims(report, {"claims": {"a": labels["claims"]["a"]}})["unsupported_claim_rate"] is None


def test_committed_dataset_sizes_and_families():
    root = Path(__file__).resolve().parents[1] / "evals"
    dev = [json.loads(s) for s in (root / "dev.jsonl").read_text(encoding="utf-8").splitlines()]
    holdout = [json.loads(s) for s in (root / "holdout.jsonl").read_text(encoding="utf-8").splitlines()]
    assert (len(dev), len(holdout)) == (10, 20)
    validate_splits(dev, holdout)


class SyntheticBaseline(ReplayBackend):
    async def baseline(self, request):
        return "人工构造基线，仅做流程检查。", await self.research(request.topic, request)


async def test_pair_records_unknown_usage_and_hides_mapping(tmp_path):
    result = await run_pair(task(), SyntheticBaseline(), ReplayBackend(), {
        "model": ReplayModel(), "store": SQLiteStore(tmp_path / "db.sqlite3"),
        "settings": {"model": "synthetic"}, "source_mode": "synthetic"})
    assert result["arms"]["baseline"]["usage"]["cost_complete"] is False
    assert result["arms"]["enhanced"]["metrics"]["citation_support_rate"] is None
    assert result["source_mode"] == "synthetic"
    pairs, mapping = export_blind_pairs([result], seed=7)
    assert pairs == export_blind_pairs([result], seed=7)[0]
    assert set(mapping["pair-0001"].values()) == {"baseline", "enhanced"}
    text = json.dumps(pairs)
    assert "baseline" not in text and "enhanced" not in text
    assert "run_id" not in text and "config_hash" not in text
