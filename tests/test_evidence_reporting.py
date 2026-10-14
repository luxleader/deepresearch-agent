import pytest

from deepresearch_app.evidence import collect_evidence
from deepresearch_app.models import EvidenceBatch, ReportClaim, ResearchPacket, ResearchReport
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
