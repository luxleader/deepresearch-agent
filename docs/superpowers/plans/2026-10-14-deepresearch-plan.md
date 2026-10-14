# AI 技术方案调研 DeepResearch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 GPT Researcher 交付一个能研究 AI 技术方案、核对关键证据、有限补搜、恢复任务并完成可复现评测的本机应用。

**Architecture:** 使用固定版本 GPT Researcher 作为基础研究引擎，适配为可替换的 ResearchBackend；范围整理、证据账本、缺口决策、持久化和报告校验属于本项目。FastAPI 提供本机任务 API 和简单页面；任务状态由单工作进程写入 SQLite，恢复使用已保存 packet。

**Tech Stack:** Python 3.12+、GPT Researcher、Pydantic、FastAPI、SQLite、pytest、基础 HTML/JavaScript；模型和搜索提供方配置后再进行真实调用。

**Spec:** `../specs/2026-10-14-deepresearch-design.md`。本文为未执行的实施计划，所有 checkbox 均未勾选。用户已指定由主代理实现、用户提需求与评估；执行方式保留为 Native，不额外要求用户选择代理编排。

## Global Constraints

- 主底座固定为 `assafelovic/gpt-researcher@3582a6841fe7dc801e2a34e34ee408641aea9bce`，Python 3.12+；依赖解析后锁定完整环境，保留 Apache-2.0 来源说明。
- 本机单进程、SQLite WAL、仅监听 `127.0.0.1`；不实现公网多租户服务。
- 运行参数默认：最多 3 轮；每轮最多 3 个研究子问题；外层并发度 2；总研究调用上限 8；单个 SDK 研究步骤超时 180 秒。
- 外层调用数不等于底座内部模型/HTTP 次数；首版不承诺货币金额硬上限。
- 未配置 API 时只能运行标注清楚的离线回放与测试，不能把回放报告声称为真实联网成果。
- 摘要、对比表、理由和局限全部从同一个 claims 账本渲染；禁止模型生成额外自由文本或引用 URL。
- `as_of` 尽力遵守并披露限制，不重建严格历史快照；已知截止日后来源不能支持“截至该日”的事实。
- 先准备 10 个开发题和 20 个留出题，按主题族隔离；真实联网另做 5 个用户验收题。
- 每个逻辑改动新增独立 `docs/changes/*.md` 并提交同一变更 ID；对应验证后同步 `luxleader/deepresearch-agent`，核对远端 SHA 和文件内容。
- `.env`、凭据、虚拟环境、运行数据库、完整会话日志和简历不进入仓库。

## Review Focus

1. 摘要/对比表的事实不能绕过证据校验：Task 2 `test_all_rendered_sections_reference_validated_claims`。
2. 日期未知或晚于 as_of 的资料不能冒充历史证据：Task 2 `test_after_cutoff_and_unknown_dates_are_explicit`。
3. 外部请求返回后进程中断会留下费用和重试窗口：Task 3 `test_reserved_call_survives_crash`、Task 4 `test_completed_steps_not_repeated_on_resume`。
4. 两个研究 worker 不能覆盖彼此结果或超过剩余预算：Task 3 `test_two_step_commits_preserve_both_packets`、Task 4 `test_concurrency_and_budget_limits`。
5. 官方资料不可达、模型结构不合法或来源正文为空时，不能发布“已验证”报告：Task 1 `test_unread_sources_are_not_evidence`、Task 2 `test_invalid_report_not_exported`、Task 5 `test_download_before_completion_returns_409`。

## File Structure

所有路径相对 `E:/codeproject/deepresearch-agent`。下表是计划创建的文件，不表示已经存在。

| 文件 | 职责 |
|---|---|
| `pyproject.toml`, `uv.lock`, `.env.example` | 锁定运行环境，声明配置入口 |
| `src/deepresearch_app/models.py`, `ports.py`, `settings.py` | 数据契约、研究/结构化模型接口、配置检查 |
| `src/deepresearch_app/backends/gptr.py`, `replay.py` | 固定 SDK 适配与明确标注的回放适配 |
| `src/deepresearch_app/evidence.py`, `reporting.py` | 来源与证据验证、全报告验证和 Markdown 渲染 |
| `src/deepresearch_app/storage.py` | SQLite 事务、调用预留、packet 和事件 |
| `src/deepresearch_app/research.py`, `prompts.py` | 研究计划、缺口判断、有界研究循环和恢复 |
| `src/deepresearch_app/api.py`, `static/index.html`, `static/app.js` | 本机接口和用户验收页面 |
| `src/deepresearch_app/evaluation.py` | 分割检查、对照运行、指标与盲评数据 |
| `tests/conftest.py`, `tests/fixtures/` | 合成小样本、假 SDK、假模型、故障注入，不含真实密钥 |
| `tests/test_contracts_backend.py`, `test_evidence_reporting.py`, `test_storage.py`, `test_research.py`, `test_api.py`, `test_evaluation.py` | 关键行为和失败场景验证 |
| `evals/dev.jsonl`, `holdout.jsonl`, `manifest.json`, `results/` | 问题与来源摘要/哈希、运行配置和结果；运行原文缓存单独忽略 |
| `scripts/run_demo.py`, `run_eval.py`, `check_change_record.py` | 演示、评测、改动文档核验 |
| `Dockerfile`, `compose.yaml`, `.github/workflows/ci.yml` | 打包、本机部署准备、无凭据 CI |
| `docs/architecture.md`, `evaluation.md`, `interview.md`, `upstream.md`, `changes/*.md` | 架构、评测解释、面试材料、来源和每次改动记录 |

## Task 1 基础契约与底座适配

**Files:** Create `pyproject.toml`, `uv.lock`, `.env.example`, `src/deepresearch_app/{__init__,models,ports,settings}.py`, `src/deepresearch_app/backends/{__init__,gptr,replay}.py`, `tests/conftest.py`, `tests/test_contracts_backend.py`, `tests/fixtures/sdk_sources.json`, `docs/upstream.md`。

**Interfaces:**
- Consumes: Spec 中全部 Pydantic 模型；固定 SDK 的 `conduct_research()`, `write_report()`, `get_research_sources()`, `get_costs()`。
- Produces: `ResearchBackend.research(question: str, request: ResearchRequest) -> ResearchPacket`（async）；`StructuredModel.generate(prompt: str, schema: type[BaseModel]) -> BaseModel`（async）。协议实现者完成 schema 实例化与校验，异常原样交给流程层记录。
- Produces: `GPTRBackend.baseline(request: ResearchRequest) -> tuple[str, ResearchPacket]`（async），仅供对照评测；baseline 的原始 Markdown 不通过产品报告下载接口发布。
- `tests/conftest.py` 提供假 SDK、确定性假结构化模型、来自合成正文的小规模 Source/Packet、临时数据库 fixture。Source 规范化和空正文过滤由本任务适配器负责。

- [ ] **Step 1 Write failing tests**：用假 SDK 固定 URL/title/raw_content 数据，不调用外网。
```python
def test_request_rejects_rounds_above_three():
    with pytest.raises(ValidationError):
        ResearchRequest(topic="混合检索", constraints={}, as_of=date(2026, 10, 14), max_rounds=4)

async def test_unread_sources_are_not_evidence(fake_backend, research_request):
    packet = await fake_backend.research("空正文与有效正文", research_request)
    assert all(source.text.strip() for source in packet.sources)
    assert isinstance(packet.context, str)
    assert packet.usage["cost_complete"] is False
```
- [ ] **Step 2 Verify red**：`uv run pytest tests/test_contracts_backend.py -q`，预期契约/适配器不存在导致失败。
- [ ] **Step 3 Implement**：建立上述模型和协议；SDK 原始字段先以固定提交源码与真实小样本确认，再收敛到自己的 schema。没有网络配置时运行明确 replay 模式；有网络配置时使用固定版本 GPTR。不将猜测的工具返回字段写成已验证事实。
- [ ] **Step 4 Verify green**：同一命令全部 PASS；单独以 `uv run python scripts/run_demo.py --mode live --question "..."` 进行一题联网集成（脚本在 Task 7 完成前可用等效模块入口）。无凭据时写“联网未验证”，仍完成离线契约验证。
- [ ] **Step 5 Record and commit**：新增独立变更文档，记录环境锁、上游提交、真实配置兼容性与验证，提交包含 `DR-<date>-NNN`（按现有记录取下一编号）；同步远端并回读。

## Task 2 证据账本与全报告校验

**Files:** Create `src/deepresearch_app/evidence.py`, `reporting.py`, `tests/test_evidence_reporting.py`；Modify `models.py`（必要时仅补 Spec 已规定的类型）。

**Interfaces:**
- Consumes: `ResearchPacket`, `Source`, `Evidence`, `ReportClaim`, `ComparisonRow`, `ResearchReport`, `ReportValidation`, `StructuredModel`。
- Produces: `collect_evidence(packet: ResearchPacket, request: ResearchRequest, model: StructuredModel) -> list[Evidence]`（async）；`validate_report(report: ResearchReport, sources: list[Source], evidence: list[Evidence]) -> ReportValidation`；`render_markdown(report: ResearchReport, sources: list[Source], evidence: list[Evidence]) -> str`。
- 稳定 Source ID 为规范化 URL + 正文哈希的摘要；同 URL 不同版本保留不同 ID。只去除明确跟踪参数，不能去掉影响内容的查询参数。quote 规范化空白后必须存在于正文；语义核验结果另存，不把“片段存在”标为“事实正确”。

- [ ] **Step 1 Write failing tests**：涵盖伪造 quote、未知 evidence ID、事实标注、摘要与表格引用路径、日期限制。
```python
def test_all_rendered_sections_reference_validated_claims(report, sources, evidence):
    report.summary_claim_ids = ["missing-claim"]
    result = validate_report(report, sources, evidence)
    assert not result.valid
    assert "missing-claim" in " ".join(result.errors)

def test_after_cutoff_and_unknown_dates_are_explicit(report, sources, evidence):
    sources[0].time_status = "after_cutoff"
    assert not validate_report(report, sources, evidence).valid
```
- [ ] **Step 2 Verify red**：`uv run pytest tests/test_evidence_reporting.py -q`，预期缺失 validator/renderer 失败。
- [ ] **Step 3 Implement**：固定格式报告只引用已存在的 claim；事实引用 supported 证据，时间适用性未知必须显式显示，截止日后证据只进入明确的补充/未知项。确定性渲染引用 URL，禁止模型自由生成链接。`render_markdown` 对 invalid 报告抛 `ValueError`，产品流程允许一次修复，仍失败只保存草稿。
- [ ] **Step 4 Verify green**：同一命令 PASS；补 `test_invalid_report_not_exported`、引用正文不包含恶意链接和关键事实误标为建议的人工抽查用例。人工抽查不以模型自评代替。
- [ ] **Step 5 Record and commit**：独立 MD 说明“原文片段存在”与“语义支持”的差异及日期语义；提交新 ID 后同步并核对。

## Task 3 持久化与崩溃恢复契约

**Files:** Create `src/deepresearch_app/storage.py`, `tests/test_storage.py`。

**Interfaces:**
- Produces: `SQLiteStore.create(request: ResearchRequest) -> ResearchState`；`get(run_id: str) -> ResearchState`；`reserve_call(run_id: str, step_key: str) -> bool`；`commit_packet(run_id: str, step_key: str, packet: ResearchPacket) -> None`；`save(state: ResearchState) -> None`；`append_event(run_id: str, stage: str, detail: dict) -> int`；`events(run_id: str, after_seq: int) -> list[dict]`。
- `reserve_call` 按事务确保 steps 唯一且预算充足，外部调用前计数持久化。重试同一 failed/interrupted 步骤要再次扣一次调用预算；completed packet 的步骤不再预留。步骤调用尝试次数单独记录。

- [ ] **Step 1 Write failing tests**：采用临时 SQLite，模拟进程重建和并发结果。
```python
def test_reserved_call_survives_crash(store, research_request):
    state = store.create(research_request)
    assert store.reserve_call(state.run_id, "r1:q0")
    reopened = SQLiteStore(store.path)
    assert reopened.get(state.run_id).calls == 1

def test_two_step_commits_preserve_both_packets(store, run, packet):
    store.reserve_call(run.run_id, "r1:q0")
    store.reserve_call(run.run_id, "r1:q1")
    store.commit_packet(run.run_id, "r1:q0", packet)
    store.commit_packet(run.run_id, "r1:q1", packet)
    assert set(store.get(run.run_id).completed_steps) == {"r1:q0", "r1:q1"}
```
- [ ] **Step 2 Verify red**：`uv run pytest tests/test_storage.py -q` 失败。
- [ ] **Step 3 Implement**：WAL、短事务、序号事件、step 状态和尝试表；`save(state)` 不允许覆盖其他已经提交的 packet/calls/events，字段更新与 packet 合并分开。凭据不写数据库，原始正文只保存在本机运行数据中。
- [ ] **Step 4 Verify green**：同一命令 PASS；加满预算预留返回 False、未知 run_id 和 seq 分页测试；实际重新打开数据库核对。
- [ ] **Step 5 Record and commit**：独立 MD 明确只能保证已保存步骤不重复；提交新 ID 后同步并核对。

## Task 4 有界研究循环与缺口补搜

**Files:** Create `src/deepresearch_app/research.py`, `prompts.py`, `tests/test_research.py`。

**Interfaces:**
- Consumes: `ResearchBackend`, `StructuredModel`, `SQLiteStore` 以及 Task 2 的三个函数。
- Produces: `make_plan(request: ResearchRequest, model: StructuredModel) -> ResearchPlan`（async）；`check_gaps(state: ResearchState, model: StructuredModel) -> GapDecision`（async）；`run_research(run_id: str, backend: ResearchBackend, model: StructuredModel, store: SQLiteStore) -> ResearchState`（async）。新任务与恢复调用同一 `run_research`，由 store 读取当前状态。
- `make_plan` 最多 3 子问题；主循环按保存的计划/轮次推进，outer semaphore=2，total calls<=8，round<=3。SDK 步骤 `asyncio.wait_for(..., timeout=180)`；超时变 failed，保留已完成步骤与状态，不自动重试。

- [ ] **Step 1 Write failing tests**：FakeBackend 记录 active/calls；FakeModel 依次返回 plan、gap、report，模拟一个失败后恢复。
```python
async def test_concurrency_and_budget_limits(run, backend, model, store):
    state = await run_research(run.run_id, backend, model, store)
    assert backend.max_active <= 2
    assert state.calls <= 8
    assert state.round <= 3

async def test_completed_steps_not_repeated_on_resume(interrupted_run, backend, model, store):
    await run_research(interrupted_run.run_id, backend, model, store)
    assert backend.calls_by_step["r1:q0"] == 0
```
- [ ] **Step 2 Verify red**：`uv run pytest tests/test_research.py -q` 失败。
- [ ] **Step 3 Implement**：Planner 整理约束与维度；调用 Task 1 引擎研究；Task 2 收集证据；GapChecker 只补缺失/冲突项；Writer 生成结构化报告；一次报告修复后仍无效则 failed。每次外部步骤完成立即提交 packet，所有状态转换和停止理由可在 events 中查看。
- [ ] **Step 4 Verify green**：同一命令 PASS；补提前充分结束、重复子问题消除、预算耗尽带限制报告、超时及错误 schema 测试。确保 SDK 内部配置经过验证，无法约束的调用不声称受到同等硬预算。
- [ ] **Step 5 Record and commit**：独立 MD 附一条成功 trace、一条失败/恢复 trace、预算统计口径；提交新 ID 后同步并核对。

## Task 5 API 与验收页面

**Files:** Create `src/deepresearch_app/api.py`, `static/index.html`, `static/app.js`, `tests/test_api.py`。

**Interfaces:** `create_app(store: SQLiteStore, backend: ResearchBackend, model: StructuredModel) -> FastAPI`；严格实现 Spec 五个端点、状态码和事件 seq。

- [ ] **Step 1 Write failing tests**：使用 FastAPI TestClient 和假依赖。
```python
def test_download_before_completion_returns_409(client, run_id):
    assert client.get(f"/api/research/{run_id}/report?format=markdown").status_code == 409

def test_resume_running_run_returns_409(client, running_run_id):
    assert client.post(f"/api/research/{running_run_id}/resume").status_code == 409
```
- [ ] **Step 2 Verify red**：`uv run pytest tests/test_api.py -q` 失败。
- [ ] **Step 3 Implement**：本机一个工作进程执行任务；app 在相同 run 上只允许一个 active runner，重启后显式恢复；页面用轮询 seq 查看进度、来源/原文、报告与错误，用户可提交问题/约束、恢复、导出。Markdown 展示使用可靠 sanitizer 或安全文本渲染，不能插入未清理的网页 HTML。
- [ ] **Step 4 Verify green**：同一命令 PASS；浏览器手工/可用自动化验证刷新不中断任务、已完成不可重复 resume、中文/长问题、错误状态和 JSON/Markdown 导出一致。接口内容测试不替代实际页面检查。
- [ ] **Step 5 Record and commit**：独立 MD 附接口验证和页面验收结果；提交新 ID 后同步并核对。

## Task 6 数据集与公平对照评测

**Files:** Create `src/deepresearch_app/evaluation.py`, `tests/test_evaluation.py`, `evals/{dev,holdout}.jsonl`, `evals/manifest.json`, `scripts/run_eval.py`, `docs/evaluation.md`。

**Interfaces:** `validate_splits(dev: list[dict], holdout: list[dict]) -> None`；`score_claims(report: ResearchReport, labels: dict) -> dict[str,float|None]`；`run_pair(task: dict, backend_a: ResearchBackend, backend_b: ResearchBackend, config: dict) -> dict`（async）；`export_blind_pairs(results: list[dict], seed: int) -> list[dict]`。

- [ ] **Step 1 Write failing tests**：使用 2 个合成题与人工 fixture，不调用模型充当唯一裁判。
```python
def test_same_topic_family_cannot_leak_across_splits(dev, holdout):
    holdout[0]["topic_family"] = dev[0]["topic_family"]
    with pytest.raises(ValueError):
        validate_splits(dev, holdout)

def test_zero_claims_not_reported_as_perfect_score(empty_report):
    assert score_claims(empty_report, {})["citation_support_rate"] is None
```
- [ ] **Step 2 Verify red**：`uv run pytest tests/test_evaluation.py -q` 失败。
- [ ] **Step 3 Implement**：10/20 按主题族分割；来源回放和记录配置哈希、截止日期、底座版本、模型设置、外层预算；A 使用基础 SDK，B 使用增强流程。人工核验覆盖率、引用支持率、未核实结论率；盲评隐藏 A/B，随机顺序可由 seed 复现。底座 token/费用未完整统计时记录 missing，不当作零。
- [ ] **Step 4 Verify green**：同一命令 PASS；运行 2 题离线回放核对结果文件和 blind mapping，用户审核标注后才执行留出集；真实联网 5 题单列。若无法统一真实底座内部模型预算，结果必须展示实际用量和费用差异，不能宣传为同 token 预算提升。
- [ ] **Step 5 Record and commit**：独立 MD 附数据 manifest、实测结果、成本缺项和无提升解释；提交新 ID 后同步并核对。不得预先填写成功率提升。

## Task 7 打包与维护交付

**Files:** Create `Dockerfile`, `compose.yaml`, `.github/workflows/ci.yml`, `scripts/run_demo.py`, `scripts/check_change_record.py`, `docs/{architecture,interview}.md`；Modify `README.md`, `docs/upstream.md`。

**Interfaces:** `check_change_record(base_ref: str, head_ref: str) -> list[str]` 返回缺少独立 MD、变更 ID 或必需记录字段的错误；CLI exit 0 表示没有错误。README 提供 live/replay 两种明确命令。

- [ ] **Step 1 Define verification fixture**：人为构造一个代码变更却没有 MD 的提交差异，检查工具必须返回错误；有完整 MD 与相同变更 ID 的差异必须通过。这个检查只覆盖文档存在/字段，不声称验证文字真实性。
- [ ] **Step 2 Verify red**：运行变更检查样例预期失败；`uv run pytest -q` 作为产品整体基线。
- [ ] **Step 3 Implement**：Docker 运行非 root，宿主只映射 localhost；CI 仅离线测试/静态检查，无生产密钥。README 说明底座与本项目新增模块；架构图、失败案例、用户验收说明与真实实验口径保存在 docs。上游来源保留许可证要求，不把上游原生能力当独立实现。
- [ ] **Step 4 Verify green**：`uv run pytest -q`、`uv run ruff check src tests scripts`、`docker compose config`；Docker 存在时实际 build/run replay，并确认 API 可用；无 Docker 时明确“容器运行未验证”。读到 actual model/search 配置后再验证 live，不把离线测试当联网成功。
- [ ] **Step 5 Record and commit**：独立 MD 记录每条实际检查、完整交付范围和未完成验证；提交新 ID、同步远端、核对 commit SHA，里程碑标签在用户验收后添加。

## 交付评审与未决条件

每个阶段交付后，用户评估真实问题上的报告，提出下一次需求；实现者把反馈写入下一份改动 MD，不改写已提交的评测结论。第一版以本设计的范围为准，新增训练、复杂 UI、公网服务或严格历史快照属于单独范围变更。

进入真实联网前需要模型提供方、模型 ID、可访问接口和搜索提供方配置。凭据只在本机环境文件配置。现在可完成离线实现、测试和回放；实际费用上限和公网部署不在用户已确认范围内。

计划自审：Spec 中工作流、证据、日期、恢复、预算、界面、评测和维护均有对应任务；数据类型引用统一；5 个 Review Focus 均有具体验证归属。计划尚未执行，不得在完成说明中把这些未来命令写成已通过。
