from concurrent.futures import ThreadPoolExecutor

import pytest

from deepresearch_app.models import ResearchPacket
from deepresearch_app.storage import SQLiteStore


def test_reserved_call_survives_crash(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    run = store.create(research_request)
    assert store.reserve_call(run.run_id, "r1:q0")
    assert SQLiteStore(store.path).get(run.run_id).calls == 1


def test_two_step_commits_preserve_both_packets(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    run = store.create(research_request)
    for key in ["r1:q0", "r1:q1"]:
        assert store.reserve_call(run.run_id, key)
        store.commit_packet(run.run_id, key, ResearchPacket(context=key))
    stale = run.model_copy(update={"stage": "review"})
    store.save(stale)
    loaded = store.get(run.run_id)
    assert loaded.calls == 2
    assert set(loaded.completed_steps) == {"r1:q0", "r1:q1"}


def test_concurrent_reservations_cannot_exceed_budget(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    research_request.max_calls = 1
    run = store.create(research_request)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda key: store.reserve_call(run.run_id, key), ["a", "b"]))
    assert sum(results) == 1
    assert store.get(run.run_id).calls == 1


def test_completed_step_cannot_be_reserved_again(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    run = store.create(research_request)
    store.reserve_call(run.run_id, "one")
    store.commit_packet(run.run_id, "one", ResearchPacket(context="saved"))
    assert not store.reserve_call(run.run_id, "one")
    assert store.get(run.run_id).calls == 1


def test_events_increment_and_filter(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "state.sqlite")
    run = store.create(research_request)
    first = store.append_event(run.run_id, "plan", {})
    second = store.append_event(run.run_id, "read", {})
    assert second > first
    assert [x["seq"] for x in store.events(run.run_id, first)] == [second]
    with pytest.raises(KeyError):
        store.get("missing")
