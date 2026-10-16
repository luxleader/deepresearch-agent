"""Human-scored comparisons; synthetic replay never measures research quality."""
import hashlib
import json
import random
import time
from pathlib import Path

from .backends.gptr import UPSTREAM_COMMIT, research_query
from .models import ResearchPacket, ResearchRequest
from .reporting import render_markdown
from .research import run_research


def validate_splits(dev, holdout):
    all_tasks = dev + holdout
    ids = [t["id"] for t in all_tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task id")
    overlap = {t["topic_family"] for t in dev} & {t["topic_family"] for t in holdout}
    if overlap:
        raise ValueError("topic_family leakage: " + ", ".join(sorted(overlap)))
    for task in all_tasks:
        ResearchRequest.model_validate({k: task[k] for k in ("topic", "constraints", "as_of")})
        if not task.get("required_dimensions"):
            raise ValueError("required_dimensions missing")


def score_claims(report, labels):
    facts = [c for c in report.claims if c.kind == "fact"]
    cited = [c for c in facts if c.evidence_ids]
    claim_labels = labels.get("claims", {})

    def rate(claims, field, invert=False):
        if not claims or any(type(claim_labels.get(c.id, {}).get(field)) is not bool for c in claims):
            return None
        values = [claim_labels[c.id][field] for c in claims]
        return sum((not v) if invert else v for v in values) / len(values)

    dimensions = labels.get("required_dimensions", [])
    covered = labels.get("covered_dimensions")
    return {"citation_support_rate": rate(cited, "citation_supported"),
            "unsupported_claim_rate": rate(facts, "fact_supported", invert=True),
            "dimension_coverage": (len(set(dimensions) & set(covered)) / len(set(dimensions)))
            if dimensions and covered is not None else None,
            "blind_score": labels.get("blind_score"), "fact_count": len(facts),
            "cited_fact_count": len(cited), "annotated_fact_count": sum(c.id in claim_labels for c in facts)}


def source_manifest(sources):
    return sorted([{"url": s.url, "content_hash": s.content_hash, "published_at": str(s.published_at),
                    "time_status": s.time_status, "version": s.version} for s in sources],
                  key=lambda s: (s["url"], s["content_hash"]))


def sum_usage(packets):
    # Completeness must be explicitly established by every provider.
    result = {"cost_complete": bool(packets) and all(p.usage.get("cost_complete") is True for p in packets)}
    for key in ("sdk_estimated_usd", "prompt_tokens", "completion_tokens"):
        values = [p.usage.get(key) for p in packets]
        result[key] = sum(values) if values and all(type(v) in (int, float) for v in values) else None
    return result


async def run_pair(task, backend_a, backend_b, config):
    request = ResearchRequest.model_validate({k: task[k] for k in ("topic", "constraints", "as_of")})
    mode = config["source_mode"]
    if mode not in {"synthetic", "frozen", "live"}:
        raise ValueError("invalid source_mode")
    safe_settings = config["settings"]
    if any("key" in k.lower() or "secret" in k.lower() for k in safe_settings):
        raise ValueError("Do not include credentials in evaluation settings")
    store, model = config["store"], config["model"]
    settings_json = json.dumps(safe_settings, sort_keys=True, ensure_ascii=False)
    fingerprint = {"task": task, "settings": safe_settings, "mode": mode, "upstream": UPSTREAM_COMMIT}
    if hasattr(backend_b, "packet"):
        fingerprint["corpus"] = source_manifest(backend_b.packet.sources)
    digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    directory = Path(config.get("cache_dir", Path(store.path).parent / "pairs"))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (digest + ".json")
    result = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "task": task, "source_mode": mode, "upstream_commit": UPSTREAM_COMMIT,
        "settings": safe_settings, "config_hash": hashlib.sha256(settings_json.encode()).hexdigest(),
        "budget": {"rounds": request.max_rounds, "outer_calls": request.max_calls, "concurrency": 2},
        "comparison_scope": "frozen corpus writing/planning" if mode == "frozen" else mode,
        "status": "pending", "attempt_errors": [],
        "arms": {"baseline": {"status": "pending"}, "enhanced": {"status": "pending"}}}

    def persist():
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def failed(arm, exc, start):
        result["arms"][arm].update(status="failed", error=f"{type(exc).__name__}: {exc}"[:1000],
                                   duration_ms=result["arms"][arm].get("duration_ms", 0) + int((time.perf_counter() - start) * 1000))
        result["status"] = "failed"
        result["attempt_errors"].append({"arm": arm, "error": result["arms"][arm]["error"]})
        persist()

    if result["arms"]["baseline"]["status"] != "completed":
        start = time.perf_counter()
        try:
            baseline, packet = await backend_a.baseline(request)
            result["arms"]["baseline"] = {"status": "completed", "report": baseline,
                "packet": packet.model_dump(mode="json"), "sources": source_manifest(packet.sources),
                "duration_ms": result["arms"]["baseline"].get("duration_ms", 0) + int((time.perf_counter() - start) * 1000),
                "usage": sum_usage([packet]), "metrics": None}
            persist()  # Paid baseline material survives every later failure.
        except Exception as exc:
            failed("baseline", exc, start)
            return result
    arm = result["arms"]["enhanced"]
    if arm["status"] != "completed":
        if "run_id" not in arm:
            arm["run_id"] = store.create(request).run_id
            persist()
        before = dict(getattr(model, "usage", {}))
        start = time.perf_counter()
        state = await run_research(arm["run_id"], backend_b, model, store)
        after = getattr(model, "usage", {})
        tokens = dict(arm.get("usage", {}).get("orchestrator_tokens") or {})
        for key in after:
            tokens[key] = tokens.get(key, 0) + after[key] - before.get(key, 0)
        usage = sum_usage(list(state.completed_steps.values()))
        usage["orchestrator_tokens"] = tokens or None
        arm.update(usage=usage, outer_calls=state.calls, sources=source_manifest(state.sources),
                   packets={key: p.model_dump(mode="json") for key, p in state.completed_steps.items()})
        if state.status != "completed":
            failed("enhanced", RuntimeError(state.error or "enhanced research failed"), start)
            return result
        try:
            if mode == "frozen" and result["arms"]["baseline"]["sources"] != source_manifest(state.sources):
                raise ValueError("Frozen comparison requires identical source corpus")
            arm.update(status="completed", report=render_markdown(state.report, state.sources, state.evidence),
                       structured_report=state.report.model_dump(mode="json"),
                       evidence=[e.model_dump(mode="json") for e in state.evidence],
                       duration_ms=arm.get("duration_ms", 0) + int((time.perf_counter() - start) * 1000),
                       metrics=score_claims(state.report, {}))
            arm.pop("error", None)
            result["status"] = "completed"
            persist()
        except Exception as exc:
            failed("enhanced", exc, start)
    return result


def export_blind_pairs(results, seed):
    rng = random.Random(seed)
    pairs, mapping = [], {}
    for i, result in enumerate(results, 1):
        pair_id = f"pair-{i:04d}"
        order = ["baseline", "enhanced"]
        rng.shuffle(order)
        mapping[pair_id] = dict(zip(("X", "Y"), order))
        pairs.append({"pair_id": pair_id, "topic": result["task"]["topic"],
                      "constraints": result["task"]["constraints"],
                      "required_dimensions": result["task"]["required_dimensions"],
                      "candidates": [{"slot": slot, "report": result["arms"][arm].get("report", "研究失败，未生成报告")}
                                     for slot, arm in mapping[pair_id].items()]})
    return pairs, mapping


class FrozenBackend:
    """Identical read material for controlled strategy comparisons."""
    mode = "live"

    def __init__(self, packet: ResearchPacket, native_backend):
        if not packet.sources or not packet.context.strip():
            raise ValueError("Frozen corpus cannot be empty")
        self.packet, self.native_backend = packet, native_backend

    async def research(self, question, request):
        return self.packet.model_copy(update={"usage": {"cost_complete": False}, "duration_ms": 0})

    async def baseline(self, request):
        sdk = self.native_backend._new_sdk(research_query(request.topic, request))
        markdown = await sdk.write_report(ext_context=self.packet.context)
        packet = self.packet.model_copy(update={"usage": {"sdk_estimated_usd": sdk.get_costs(), "cost_complete": False}})
        return markdown, packet
