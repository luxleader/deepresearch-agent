import argparse
import asyncio
from pathlib import Path

from deepresearch_app.backends.gptr import GPTRBackend
from deepresearch_app.backends.replay import ReplayBackend, ReplayModel
from deepresearch_app.models import ResearchRequest
from deepresearch_app.providers import JSONModel
from deepresearch_app.reporting import render_markdown
from deepresearch_app.research import run_research
from deepresearch_app.settings import Settings
from deepresearch_app.storage import SQLiteStore


async def main(args):
    settings = Settings.from_env()
    if args.mode == "live":
        settings.validate_live()
        backend, model = GPTRBackend(settings), JSONModel(settings)
    else:
        backend, model = ReplayBackend(), ReplayModel()
    store = SQLiteStore(settings.database)
    state = store.create(ResearchRequest(topic=args.question, constraints={"预算": args.budget}))
    state = await run_research(state.run_id, backend, model, store)
    if state.status != "completed":
        raise RuntimeError(state.error or "Research did not complete")
    path = Path("runtime/reports") / (state.run_id + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_markdown(state.report, state.sources, state.evidence)
    if args.mode == "replay":
        content = "> 离线人工构造回放，不是真实联网研究。\n\n" + content
    path.write_text(content, encoding="utf-8")
    print(f"Report: {path.resolve()} | mode={args.mode} | rounds={state.round} | outer_calls={state.calls}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["replay", "live"], default="replay")
    parser.add_argument("--question", default="中文 PDF 知识库如何选择检索方案？")
    parser.add_argument("--budget", default="有限")
    asyncio.run(main(parser.parse_args()))
