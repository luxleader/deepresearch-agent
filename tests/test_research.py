import asyncio

from deepresearch_app.backends.replay import ReplayBackend, ReplayModel
from deepresearch_app.research import run_research
from deepresearch_app.storage import SQLiteStore


class TrackingBackend(ReplayBackend):
    def __init__(self, fail_once=False, delay=0):
        self.active = 0
        self.maximum = 0
        self.fail_once = fail_once
        self.delay = delay
        self.questions = []

    async def research(self, question, request):
        self.questions.append(question)
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        try:
            await asyncio.sleep(self.delay)
            if self.fail_once and "约束核对" in question:
                self.fail_once = False
                raise RuntimeError("故障注入")
            return await super().research(question, request)
        finally:
            self.active -= 1


async def test_concurrency_and_budget_limits(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    run = store.create(research_request)
    backend = TrackingBackend(delay=0.01)
    result = await run_research(run.run_id, backend, ReplayModel(), store)
    assert result.status == "completed"
    assert backend.maximum <= 2
    assert result.calls <= 8
    assert result.round == 2
    assert len(result.sources) == 3


async def test_completed_steps_not_repeated_on_resume(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    run = store.create(research_request)
    backend = TrackingBackend(fail_once=True)
    failed = await run_research(run.run_id, backend, ReplayModel(), store)
    assert failed.status == "failed"
    saved_question = failed.round_questions["1"][0]
    restored = await run_research(run.run_id, backend, ReplayModel(), store)
    assert restored.status == "completed"
    assert backend.questions.count(saved_question) == 1
    assert restored.calls == 4


async def test_budget_exhaustion_produces_limited_report(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    research_request.max_calls = 1
    run = store.create(research_request)
    result = await run_research(run.run_id, ReplayBackend(), ReplayModel(), store)
    assert result.status == "completed"
    assert result.calls == 1
    assert any("预算" in warning for warning in result.warnings)
    assert result.report.limitation_claim_ids


async def test_timeout_persists_failed_run(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    run = store.create(research_request)
    result = await run_research(run.run_id, TrackingBackend(delay=1), ReplayModel(), store, timeout=0.01)
    assert result.status == "failed"
    assert store.get(run.run_id).calls == 2


async def test_completed_run_does_not_spend_again(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    run = store.create(research_request)
    backend = TrackingBackend()
    first = await run_research(run.run_id, backend, ReplayModel(), store)
    again = await run_research(run.run_id, backend, ReplayModel(), store)
    assert again.calls == first.calls
    assert len(backend.questions) == first.calls
