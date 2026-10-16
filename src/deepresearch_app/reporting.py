import re

from .evidence import normalize_text
from .models import ReportValidation
from .network import validate_public_url


def validate_report(report, sources, evidence):
    errors = []
    source_map = {s.id: s for s in sources}
    evidence_map = {e.id: e for e in evidence}
    claim_map = {c.id: c for c in report.claims}
    if len(claim_map) != len(report.claims):
        errors.append("重复 claim ID")
    if len(evidence_map) != len(evidence):
        errors.append("重复 evidence ID")
    references = report.summary_claim_ids + report.limitation_claim_ids
    for row in report.comparison:
        references.append(row.label)
        references.extend(row.aspects)
        for ids in row.aspects.values():
            references += ids
    for cid in references:
        if cid not in claim_map:
            errors.append("未知 claim: " + cid)
    for cid in report.limitation_claim_ids:
        if cid in claim_map and claim_map[cid].kind != "uncertainty":
            errors.append("局限必须使用 uncertainty claim: " + cid)
    for claim in report.claims:
        if re.search(r"https?://|\]\(", claim.text):
            errors.append("claim 禁止自行生成链接: " + claim.id)
        support = []
        for eid in claim.evidence_ids:
            item = evidence_map.get(eid)
            source = source_map.get(item.source_id) if item else None
            if item is None or source is None:
                errors.append("未知或缺失 evidence/source: " + eid)
                continue
            try:
                validate_public_url(source.url, resolve=False)
            except ValueError:
                errors.append("非法来源 URL: " + eid)
                continue
            if not normalize_text(item.quote) or not normalize_text(source.text) or normalize_text(item.quote) not in normalize_text(source.text):
                errors.append("原文片段不存在: " + eid)
                continue
            if item.verdict == "supported" and source.time_status != "after_cutoff":
                support.append(item)
        if claim.kind == "fact":
            if not support:
                errors.append("事实缺少 supported 证据: " + claim.id)
            elif all(normalize_text(claim.text) != normalize_text(e.claim) for e in support):
                errors.append("事实必须复用已核验的命题，禁止偷换结论: " + claim.id)
    return ReportValidation(valid=not errors, errors=errors)


def escape(text):
    return re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", str(text)).replace("\n", " ")


def report_export(state):
    if state.status != "completed" or state.report is None:
        raise ValueError("研究尚未完成")
    validation = validate_report(state.report, state.sources, state.evidence)
    if not validation.valid:
        raise ValueError("；".join(validation.errors))
    return {"schema_version": 1, "mode": state.mode, "run_id": state.run_id,
            "request": state.request.model_dump(mode="json"),
            "plan": state.plan.model_dump(mode="json") if state.plan else None,
            "created_at": state.created_at.isoformat(), "completed_at": state.updated_at.isoformat(),
            "warnings": state.warnings, "rounds": state.round, "outer_calls": state.calls,
            "sources": [s.model_dump(mode="json") for s in state.sources],
            "evidence": [e.model_dump(mode="json") for e in state.evidence],
            "research_steps": [{"step": key, "duration_ms": p.duration_ms, "usage": p.usage}
                               for key, p in state.completed_steps.items()],
            "usage_complete": False,
            "usage_scope": "仅列已保存研究步骤的已知用量；不包括完整规划/核验/写作用量及失败请求费用，不是总费用。",
            **state.report.model_dump(mode="json")}


def render_markdown(report, sources, evidence):
    validation = validate_report(report, sources, evidence)
    if not validation.valid:
        raise ValueError("；".join(validation.errors))
    claims = {c.id: c for c in report.claims}
    emap = {e.id: e for e in evidence}
    smap = {s.id: s for s in sources}

    def line(cid):
        claim = claims[cid]
        tag = {"fact": "事实", "recommendation": "建议", "uncertainty": "未知/局限"}[claim.kind]
        refs = " ".join(f"[{escape(eid)}]" for eid in claim.evidence_ids)
        return f"{tag}：{escape(claim.text)} {refs}".strip()

    text = ["# AI 技术方案调研报告", "", "## 结论摘要", ""]
    text.extend("- " + line(cid) for cid in report.summary_claim_ids)
    if report.comparison:
        text.extend(["", "## 方案对比", ""])
        for row in report.comparison:
            text.append("### " + line(row.label))
            for name, ids in row.aspects.items():
                text.append("- " + line(name) + "：" + "；".join(line(cid) for cid in ids))
    text.extend(["", "## 核验命题与建议", ""])
    text.extend("- " + line(c.id) for c in report.claims if c.id not in report.limitation_claim_ids)
    text.extend(["", "## 局限与未知项", ""])
    text.extend("- " + line(cid) for cid in report.limitation_claim_ids)
    text.extend(["", "## 引用与证据", ""])
    used = dict.fromkeys(eid for c in report.claims for eid in c.evidence_ids)
    for eid in used:
        e = emap[eid]
        s = smap[e.source_id]
        text.extend([f"- [{escape(eid)}] [{escape(s.title)}]({s.url})", f"  原文：{escape(e.quote)}",
                     f"  支持判断：{e.verdict}；{escape(e.reason)}（模型判断需人工抽查）"])
        text.append(f"  发布日期：{s.published_at or '未知'}；修改日期：{s.modified_at or '未知'}；版本：{escape(s.version or '未知')}。")
        if s.date_basis:
            text.append("  日期依据：" + escape(s.date_basis) + "（站点声明，未独立验证）。")
        for warning in s.metadata_warnings:
            text.append("  来源提示：" + escape(warning))
        if s.time_status == "unknown":
            text.append("  时间适用性未核实；抓取时间不代表发布日期。")
        if s.time_status == "after_cutoff":
            text.append("  资料晚于截止日期，仅列为补充。")
    return "\n".join(text) + "\n"
