"""Run two smoke pairs by default. Results and blind mapping stay local."""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from deepresearch_app.backends.gptr import GPTRBackend
from deepresearch_app.backends.replay import ReplayBackend, ReplayModel
from deepresearch_app.evaluation import FrozenBackend, export_blind_pairs, run_pair, validate_splits
from deepresearch_app.models import ResearchPacket
from deepresearch_app.providers import JSONModel
from deepresearch_app.settings import Settings
from deepresearch_app.storage import SQLiteStore


class SyntheticBaseline(ReplayBackend):
    async def baseline(self, request):
        return "人工构造基线报告：仅用于比较文件生成与盲评顺序的流程测试。", await self.research(request.topic, request)


def read_tasks(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def main(args):
    root = Path(__file__).resolve().parents[1]
    dev, holdout = read_tasks(root / "evals/dev.jsonl"), read_tasks(root / "evals/holdout.jsonl")
    validate_splits(dev, holdout)
    if args.split == "holdout" and not args.approved_holdout:
        raise ValueError("留出集需由用户审核题目与标注协议后，加 --approved-holdout 显式执行")
    if args.mode == "frozen" and not args.corpus:
        raise ValueError("--mode frozen 必须提供 --corpus 本机 ResearchPacket JSON")
    tasks = dev if args.split == "dev" else holdout if args.split == "holdout" else read_tasks(root / "evals/online.jsonl")
    output = Path(args.output or "runtime/evals/" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    output.mkdir(parents=True, exist_ok=True)
    if args.mode == "synthetic":
        a, b, model, settings = SyntheticBaseline(), ReplayBackend(), ReplayModel(), {"model": "synthetic"}
    else:
        configuration = Settings.from_env()
        configuration.validate_live()
        a, model = GPTRBackend(configuration), JSONModel(configuration)
        b = a
        if args.mode == "frozen":
            packet = ResearchPacket.model_validate_json(Path(args.corpus).read_text(encoding="utf-8"))
            a = b = FrozenBackend(packet, a)
        settings = {"model": configuration.model, "api_base": configuration.api_base, "temperature": 0}
    results = []
    for task in tasks[:args.limit]:
        results.append(await run_pair(task, a, b, {"model": model, "store": SQLiteStore(output / "runs.sqlite3"),
                                                  "settings": settings, "source_mode": args.mode}))
    pairs, mapping = export_blind_pairs(results, args.seed)
    for name, data in (("results.json", results), ("blind-pairs.json", pairs), ("private-mapping.json", mapping)):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存 {len(results)} 对结果至 {output.resolve()}；无人工标注，质量指标未评分。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["synthetic", "frozen", "live"], default="synthetic")
    parser.add_argument("--split", choices=["dev", "holdout", "online"], default="dev")
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output")
    parser.add_argument("--corpus")
    parser.add_argument("--approved-holdout", action="store_true")
    asyncio.run(main(parser.parse_args()))
