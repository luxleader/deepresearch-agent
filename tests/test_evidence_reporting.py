import pytest

from deepresearch_app.evidence import collect_evidence
from deepresearch_app.models import ComparisonRow, EvidenceBatch, ReportClaim, ResearchPacket, ResearchReport
from deepresearch_app.reporting import render_markdown, validate_report


def good_report():
    return ResearchReport(title="方案调研", summary_claim_ids=["c1"], claims=[
        ReportClaim(id="c1", text="向量检索使用嵌入表示。", kind="fact", evidence_ids=["e1"])])


def test_all_rendered_sections_reference_validated_claims(sources, evidence):
    report = good_report()
    report.summary_claim_ids = ["missing-claim"]
    assert not validate_report(report, sources, evidence).valid


def test_invalid_report_not_exported(sources, evidence):
    report = good_report()
    report.claims[0].evidence_ids = ["fake"]
    with pytest.raises(ValueError):
        render_markdown(report, sources, evidence)


def test_forged_quote_rejected(sources, evidence):
    evidence[0].quote = "This text never existed."
    assert not validate_report(good_report(), sources, evidence).valid


def test_after_cutoff_and_unknown_dates_are_explicit(sources, evidence):
    sources[0].time_status = "after_cutoff"
    assert not validate_report(good_report(), sources, evidence).valid
    sources[0].time_status = "unknown"
    assert "时间适用性未核实" in render_markdown(good_report(), sources, evidence)


def test_contradicted_evidence_cannot_support_fact(sources, evidence):
    evidence[0].verdict = "contradicted"
    assert not validate_report(good_report(), sources, evidence).valid


def test_references_rendered_from_real_source(sources, evidence):
    text = render_markdown(good_report(), sources, evidence)
    assert "https://example.org/synthetic" in text
    assert "[e1]" in text


class ForgingModel:
    async def generate(self, prompt, schema):
        return EvidenceBatch(evidence=[{"id": "fake", "source_id": "s1", "quote": "fabricated", "claim": "虚构", "verdict": "supported", "reason": "模型猜测"}])


async def test_collector_downgrades_nonexistent_quote(sources, research_request):
    result = await collect_evidence(ResearchPacket(context="", sources=sources), research_request, ForgingModel())
    assert result[0].verdict == "uncertain"


def test_comparison_metadata_cannot_bypass_claim_ledger(sources, evidence):
    report = good_report()
    report.comparison = [ComparisonRow(label="此方案性能提高十倍", aspects={"预算降低90%": ["c1"]})]
    assert not validate_report(report, sources, evidence).valid


def test_whitespace_quote_cannot_support_fact(sources, evidence):
    evidence[0].quote = " \n\t "
    assert not validate_report(good_report(), sources, evidence).valid


async def test_collector_downgrades_whitespace_quote(sources, research_request):
    class BlankModel:
        async def generate(self, prompt, schema):
            batch = EvidenceBatch(evidence=[{"id": "blank", "source_id": "s1", "quote": "initial",
                                           "claim": "命题", "verdict": "supported", "reason": "guess"}])
            batch.evidence[0].quote = " \n "
            return batch
    result = await collect_evidence(ResearchPacket(context="", sources=sources), research_request, BlankModel())
    assert result[0].verdict == "uncertain"


def test_comparison_uses_claim_ids_for_every_label(sources, evidence):
    report = good_report()
    report.comparison = [ComparisonRow(label="c1", aspects={"c1": ["c1"]})]
    assert validate_report(report, sources, evidence).valid
    assert "### 事实：" in render_markdown(report, sources, evidence)
