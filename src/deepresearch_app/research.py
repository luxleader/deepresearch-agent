import asyncio

from .evidence import collect_evidence, normalize_text
from .models import GapDecision, ReportClaim, ResearchPlan, ResearchReport
from .prompts import gaps_prompt, plan_prompt, report_prompt
from .reporting import validate_report


async def make_plan(request, model):
    return await model.generate(plan_prompt(request), ResearchPlan)


async def check_gaps(state, model):
    return await model.generate(gaps_prompt(state), GapDecision)


async def run_research(run_id, backend, model, store, *, timeout=180):
    state = store.get(run_id)
    if state.status == "completed" or not store.claim_run(run_id):
        return state
    semaphore = asyncio.Semaphore(2)

    def save(stage):
        state.stage = stage
        store.save(state)
        store.append_event(run_id, stage, {"round": state.round, "calls": store.get(run_id).calls})

    async def generate(prompt, schema):
        return await asyncio.wait_for(model.generate(prompt, schema), timeout=180)

    try:
        state.status = "running"
        state.error = None
        state.mode = backend.mode
        if state.mode == "replay" and "离线回放，不是真实联网结果" not in state.warnings:
            state.warnings.append("离线回放，不是真实联网结果")
        save("planning")
        if state.plan is None:
            state.plan = await generate(plan_prompt(state.request), ResearchPlan)
            state.round = 1
            state.round_questions["1"] = list(dict.fromkeys(state.plan.questions))
            save("research")
        while state.round <= state.request.max_rounds:
            questions = state.round_questions[str(state.round)]
            save("research")

            async def execute(index, question):
                key = f"r{state.round}:q{index}"
                async with semaphore:
                    if key in store.get(run_id).completed_steps:
                        return None
                    if not store.reserve_call(run_id, key):
                        return None
                    store.append_event(run_id, "step_started", {"step": key, "question": question})
                    try:
                        packet = await asyncio.wait_for(backend.research(question, state.request), timeout=timeout)
                        store.commit_packet(run_id, key, packet)
                        store.append_event(run_id, "step_completed", {"step": key, "sources": len(packet.sources)})
                    except BaseException:
                        store.fail_step(run_id, key)
                        raise

            outcomes = await asyncio.gather(*(execute(i, q) for i, q in enumerate(questions)), return_exceptions=True)
            state = store.get(run_id)
            smap = {s.id: s for s in state.sources}
            emap = {e.id: e for e in state.evidence}
            for key, packet in state.completed_steps.items():
                for source in packet.sources:
                    smap[source.id] = source
                if key not in state.reviewed_steps:
                    if packet.sources:
                        for e in await collect_evidence(packet, state.request, model):
                            emap[e.id] = e
                    state.reviewed_steps.append(key)
                    state.sources = list(smap.values())
                    state.evidence = list(emap.values())
                    save("review")
            error = next((x for x in outcomes if isinstance(x, BaseException)), None)
            if error is not None:
                raise error
            state.gap = await generate(gaps_prompt(state), GapDecision)
            save("gaps")
            if state.gap.complete:
                break
            if state.calls >= state.request.max_calls or state.round >= state.request.max_rounds:
                state.warnings.append("研究预算已耗尽，仍可能存在信息缺口")
                break
            seen = {normalize_text(q) for qs in state.round_questions.values() for q in qs}
            followups = [q for q in dict.fromkeys(state.gap.followups) if normalize_text(q) not in seen]
            if not followups:
                state.warnings.append("没有新的可执行补搜问题，保留未解决的信息缺口")
                break
            state.round += 1
            state.round_questions[str(state.round)] = followups
            save("research")
        save("writing")
        state.report = await generate(report_prompt(state), ResearchReport)
        result = validate_report(state.report, state.sources, state.evidence)
        if not result.valid:
            state.report = await generate(report_prompt(state, result.errors), ResearchReport)
            result = validate_report(state.report, state.sources, state.evidence)
        if not result.valid:
            raise ValueError("报告核验失败：" + "; ".join(result.errors))
        for index, warning in enumerate(dict.fromkeys(state.warnings)):
            cid = f"system-limit-{index}"
            existing = {claim.id for claim in state.report.claims}
            while cid in existing:
                cid += "-system"
            state.report.claims.append(ReportClaim(id=cid, text=warning, kind="uncertainty"))
            state.report.limitation_claim_ids.append(cid)
        result = validate_report(state.report, state.sources, state.evidence)
        if not result.valid:
            raise ValueError("最终报告核验失败：" + "; ".join(result.errors))
        state.status = "completed"
        save("completed")
    except asyncio.CancelledError:
        state = store.get(run_id)
        state.status = "interrupted"
        state.error = "任务已中断，请恢复"
        store.save(state)
        raise
    except Exception as exc:
        state.status = "failed"
        state.error = f"{type(exc).__name__}: {exc}"[:1000]
        save("failed")
        store.append_event(run_id, "error", {"message": state.error})
    finally:
        store.release_run(run_id)
    return store.get(run_id)
