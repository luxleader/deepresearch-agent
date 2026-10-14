import hashlib
import json
from datetime import date

from ..models import EvidenceBatch, GapDecision, ResearchPacket, ResearchPlan, ResearchReport, Source


class ReplayBackend:
    """Synthetic offline fixtures. Never a web research or quality benchmark."""

    mode = "replay"

    async def research(self, question, request):
        suffix = question.split("｜")[-1]
        texts = {"方案依据": "演示素材：检索方案需要比较关键词匹配与语义匹配两种能力。",
                 "约束核对": "演示素材：预算、数据格式和更新方式是此测试场景的约束维度。",
                 "资料局限": "演示素材：本场景资料由人工构造，不能用来评价实际技术方案。"}
        text = texts.get(suffix, "演示素材：此输入没有对应的真实联网资料，只演示执行过程。")
        digest = hashlib.sha256(text.encode()).hexdigest()
        source = Source(id="s-" + digest[:16], url="https://example.org/synthetic/" + digest[:12],
                        title="人工构造离线素材 · " + suffix, text=text, content_hash=digest,
                        source_type="synthetic", published_at=date(2026, 1, 1),
                        time_status="within_cutoff" if request.as_of >= date(2026, 1, 1) else "after_cutoff")
        return ResearchPacket(context=text, sources=[source], usage={"synthetic": True, "cost_complete": False})


class ReplayModel:
    async def generate(self, prompt, schema):
        if schema is EvidenceBatch:
            payload = json.loads(prompt.split("\n")[-1])
            return EvidenceBatch(evidence=[{"id": "temporary", "source_id": s["id"], "quote": s["text"],
                                            "claim": s["text"], "verdict": "supported",
                                            "reason": "人工构造回放标签；未进行真实模型语义核验"}
                                           for s in payload["sources"]])
        payload = json.loads(prompt.split("\n", 1)[1])
        if schema is ResearchPlan:
            request = payload["request"]
            return ResearchPlan(questions=[request["topic"] + "｜方案依据", request["topic"] + "｜约束核对"],
                                required_dimensions=["方案依据", *request["constraints"].keys(), "局限"])
        state = payload["state"]
        if schema is GapDecision:
            complete = state["round"] >= 2
            return GapDecision(complete=complete,
                               followups=[] if complete else [state["request"]["topic"] + "｜资料局限"],
                               reason="人工构造的两轮回放策略，不能证明真实研究充分性")
        if schema is ResearchReport:
            claims = [{"id": "c-" + e["id"], "text": e["claim"], "kind": "fact", "evidence_ids": [e["id"]]}
                      for e in state["evidence"] if e["verdict"] == "supported"]
            claims.append({"id": "offline", "text": "离线回放仅验证流程，不是联网调研结论或模型效果评测。",
                           "kind": "uncertainty", "evidence_ids": []})
            return ResearchReport(title="离线研究流程演示", summary_claim_ids=[c["id"] for c in claims],
                                  claims=claims, limitation_claim_ids=["offline"])
        raise ValueError("不支持的回放 schema")
