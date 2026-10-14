# AI 技术方案调研 DeepResearch

本项目用于根据使用约束研究 AI 技术方案，查询官方文档和论文，输出可追溯的方案对比与建议。

当前已实现本机工作台、约束规划、证据校验、缺口补搜、任务恢复与评测工具。离线流程可运行，Qwen-Plus＋Tavily 已提供配置；真实联网研究、人工质量对照与容器运行尚未验证。人工构造回放不代表真实调研效果。

## 本机运行

需要 Python 3.12 与 uv，在项目目录执行：

```powershell
uv sync --frozen --python 3.12
Copy-Item .env.example .env
uv run python -m deepresearch_app
```

打开 http://127.0.0.1:8765 。默认 DR_MODE=replay，无需密钥，页面标注人工构造回放。也可先安装包 `python -m pip install -e .` 再运行模块或脚本。

```powershell
uv run python scripts/run_demo.py --mode replay
uv run python scripts/run_eval.py --mode synthetic --limit 2
uv run pytest -q
uv run ruff check src tests scripts
```

## Qwen-Plus＋Tavily

在阿里云百炼与 Tavily 控制台准备接口密钥，确认 qwen-plus 可用并取得账号区域/空间对应的兼容 base URL。示例地址需按控制台修改，密钥只填本机 .env，不发到聊天或提交 Git。

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-live.txt
```

Linux/macOS 使用 `.venv/bin/python`。SDK 固定上游提交，传递依赖尚未单独完整锁定。编辑 .env 后重新启动：

```dotenv
DR_MODE=live
DR_PROVIDER=qwen
DR_MODEL=qwen-plus
OPENAI_BASE_URL=你的兼容接口地址
OPENAI_API_KEY=只在本机填写
TAVILY_API_KEY=只在本机填写
```

代码设置 enable_thinking=false，JSON 输出经 Pydantic 校验；模拟请求测试不证明真实模型与 SDK 兼容性。联网命令：`uv run python scripts/run_demo.py --mode live --question "你的技术问题"`，缺少配置时显式报错。

## 能力与边界

默认最多 3 轮、2 个并发研究步骤、8 次外层研究调用、每步 180 秒。这些数不等于底座内部模型/HTTP 请求数，也不是硬性金额预算。SQLite 调用前预留，恢复只跳过已保存成功步骤；外部成功请求未保存的窗口仍可能重复付费。

片段存在检查和模型语义判断分别保存，事实须复用证据账本中的命题；摘要、表格和正文统一校验。无日期资料明确标注时间适用性未知，不能当成历史快照。模型判断需人工抽查，建议中的隐含事实也应核对。

来源读取支持 HTML 与 PDF 前 20 页、8MB 上限，无 OCR；动态网页、扫描件和反爬可能没有正文。优先官方文档和论文由规划提示要求，来源属性与事实仍需人工审核。

本机单进程、单用户，无公网认证；不要运行多个 worker 或公开端口。Docker/Compose 只准备离线模式、非 root 进程和宿主 localhost 映射，此环境未实际构建。

| 接口 | 行为 |
|---|---|
| POST /api/research | 创建，202 |
| GET /api/research/{id} | 查询状态 |
| GET /api/research/{id}/events?after_seq=0 | 增量事件 |
| POST /api/research/{id}/resume | 显式恢复；运行中、完成或模式不同返回 409 |
| GET /api/research/{id}/report?format=markdown 或 json | 完成且校验通过才可下载，否则 409 |

10 个开发题和 20 个留出题按主题族隔离，5 个联网验收候选题单列。未标注指标为 null，冻结来源实验仅评价材料给定时的策略；真实联网单独记录来源漂移、失败和用量，见评测协议。

## 项目资料

- [项目设计](docs/superpowers/specs/2026-10-14-deepresearch-design.md)
- [实施计划](docs/superpowers/plans/2026-10-14-deepresearch-plan.md)
- [维护约定](AGENTS.md)
- [上游选型与来源](docs/upstream.md)
- [改动记录](docs/changes/README.md)
- [架构](docs/architecture.md)、[评测](docs/evaluation.md)、[讲解与验收](docs/interview.md)

## 交付阶段

| 阶段 | 交付与验收 | 状态 |
|---|---|---|
| 基础原型 | 固定底座、配置检查、研究链路 | 离线通过；联网待验收 |
| 可追溯报告 | 原文证据、引用核验和结构化报告 | 工程实现；人工抽查待执行 |
| 深度研究 | 信息缺口补搜、有界执行和恢复 | 离线验证 |
| 产品演示 | 本机页面、进度、报告和导出 | 浏览器离线验证 |
| 评测与项目材料 | 对照实验、失败案例、打包和说明 | 工具已实现；质量未评分 |

## 开源基础

主底座选用 [GPT Researcher](https://github.com/assafelovic/gpt-researcher)，固定提交 `3582a6841fe7dc801e2a34e34ee408641aea9bce`。复用其检索、研究与原生报告接口，本项目新增约束规划、证据账本、校验、缺口循环、恢复、界面和评测；这些工程改进不宣称学术首创。

用户负责需求与结果评估，Codex 负责实现和测试。项目成果与贡献按实际过程记录。

## 更新与备份

每次独立改动对应一份 Markdown 记录和一个包含变更 ID 的提交。变更文档记录实际检查、限制和回退方法；远端同步完成后回读核验。运行密钥、数据库及完整日志不进入公开仓库。
