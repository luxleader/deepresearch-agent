import time

from fastapi.testclient import TestClient

from deepresearch_app.api import create_app
from deepresearch_app.backends.replay import ReplayBackend, ReplayModel
from deepresearch_app.storage import SQLiteStore


def test_download_before_completion_returns_409(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "api.sqlite")
    run = store.create(research_request)
    with TestClient(create_app(store, ReplayBackend(), ReplayModel())) as client:
        assert client.get(f"/api/research/{run.run_id}/report?format=markdown").status_code == 409


def test_full_api_flow_export_and_completed_resume(tmp_path):
    with TestClient(create_app(SQLiteStore(tmp_path / "api.sqlite"), ReplayBackend(), ReplayModel())) as client:
        response = client.post("/api/research", json={"topic": "企业知识库怎么选检索方案", "constraints": {"预算": "有限"}})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        for _ in range(200):
            state = client.get(f"/api/research/{run_id}").json()
            if state["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)
        assert state["status"] == "completed"
        result = client.get(f"/api/research/{run_id}/report?format=markdown")
        assert result.status_code == 200
        assert "离线" in result.text
        assert client.post(f"/api/research/{run_id}/resume").status_code == 409
        assert client.get(f"/api/research/{run_id}/report?format=json").json()["claims"]
        assert client.get(f"/api/research/{run_id}/events?after_seq=0").json()["events"]


def test_resume_running_run_returns_409(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "api.sqlite")
    app = create_app(store, ReplayBackend(), ReplayModel())
    with TestClient(app) as client:
        run = store.create(research_request)
        run.status = "running"
        store.save(run)
        assert client.post(f"/api/research/{run.run_id}/resume").status_code == 409


def test_invalid_input_and_missing_run(tmp_path):
    with TestClient(create_app(SQLiteStore(tmp_path / "api.sqlite"), ReplayBackend(), ReplayModel())) as client:
        assert client.post("/api/research", json={"topic": " "}).status_code == 422
        assert client.get("/api/research/missing").status_code == 404
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200


def test_restart_marks_interrupted_without_auto_execution(tmp_path, research_request):
    store = SQLiteStore(tmp_path / "api.sqlite")
    run = store.create(research_request)
    store.claim_run(run.run_id)
    with TestClient(create_app(store, ReplayBackend(), ReplayModel())) as client:
        state = client.get(f"/api/research/{run.run_id}").json()
        assert state["status"] == "interrupted"
        assert state["calls"] == 0
