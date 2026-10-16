import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import ResearchRequest
from .reporting import render_markdown, report_export, validate_report
from .research import run_research


def create_app(store, backend, model, *, step_timeout=180):
    tasks = {}

    @asynccontextmanager
    async def lifespan(app):
        store.recover_interrupted()
        yield
        for task in list(tasks.values()):
            task.cancel()
        await asyncio.gather(*list(tasks.values()), return_exceptions=True)

    app = FastAPI(title="AI 技术方案调研", lifespan=lifespan)

    @app.middleware("http")
    async def current_local_content(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    static = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static), name="static")

    def get(run_id):
        try:
            return store.get(run_id)
        except KeyError:
            raise HTTPException(404, "研究任务不存在") from None

    def launch(run_id):
        task = asyncio.create_task(run_research(run_id, backend, model, store, timeout=step_timeout))
        tasks[run_id] = task
        task.add_done_callback(lambda completed: tasks.pop(run_id, None))

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    @app.get("/api/health")
    def health():
        return {"mode": backend.mode, "default_as_of": ResearchRequest(topic="日期").as_of.isoformat(),
                "notice": "人工构造回放，不是真实联网研究" if backend.mode == "replay" else "联网模式，证据支持判断需人工抽查"}

    @app.post("/api/research", status_code=202)
    async def create(request: ResearchRequest):
        state = store.create(request, mode=backend.mode)
        launch(state.run_id)
        return {"run_id": state.run_id, "mode": state.mode}

    @app.get("/api/research/{run_id}")
    def status(run_id: str):
        return get(run_id)

    @app.get("/api/research/{run_id}/events")
    def events(run_id: str, after_seq: int = Query(default=0, ge=0)):
        get(run_id)
        return {"events": store.events(run_id, after_seq)}

    @app.post("/api/research/{run_id}/resume", status_code=202)
    async def resume(run_id: str):
        state = get(run_id)
        if state.status in {"running", "completed"} or run_id in tasks:
            raise HTTPException(409, "运行中或已完成的任务不能恢复")
        if state.mode != backend.mode:
            raise HTTPException(409, "任务模式与当前引擎不同，请切回原模式或创建新任务")
        launch(run_id)
        return {"run_id": run_id}

    @app.get("/api/research/{run_id}/report")
    def report(run_id: str, format: Literal["markdown", "json"] = "markdown"):
        state = get(run_id)
        if state.status != "completed" or state.report is None:
            raise HTTPException(409, "尚无已完成且通过结构核验的报告")
        if not validate_report(state.report, state.sources, state.evidence).valid:
            raise HTTPException(409, "报告校验未通过")
        if format == "json":
            return JSONResponse(report_export(state), headers={"Content-Disposition": f'attachment; filename="research-{run_id}.json"'})
        text = render_markdown(state.report, state.sources, state.evidence)
        if state.mode == "replay":
            text = "> 离线人工构造回放，不是真实联网研究或模型效果评测。\n\n" + text
        return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="research-{run_id}.md"'})

    return app


def default_app():
    from .backends.gptr import GPTRBackend
    from .backends.replay import ReplayBackend, ReplayModel
    from .providers import JSONModel
    from .settings import Settings
    from .storage import SQLiteStore

    settings = Settings.from_env()
    if settings.mode == "live":
        settings.validate_live()
        backend, model = GPTRBackend(settings), JSONModel(settings)
    else:
        backend, model = ReplayBackend(), ReplayModel()
    return create_app(SQLiteStore(settings.database), backend, model, step_timeout=settings.step_timeout)
