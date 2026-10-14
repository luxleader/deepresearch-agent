# AI 技术方案调研 DeepResearch 项目设计

日期：2026-10-14。状态：供用户评审的完整设计；尚未开始产品实现。

## 已确认的需求

用户已掌握采购 Agent，希望新增一个真实的 DeepResearch 项目。用户明确委托 Codex 实现、测试和部署准备，自己负责提需求与评估。第一版研究场景已确认是 AI 技术方案调研：查官方文档和论文，比较方案并给出有引用的建议。用户未给出上线日期、模型账号、搜索账号和费用上限；这些不能被视为已批准的费用或部署安排。

项目成果应包含可运行演示、能追溯的研究过程、可复现评测、设计说明和真实实验记录，帮助用户理解系统并在面试中解释自己的需求、设计评审和验收贡献。

## 目标行为

输入研究问题、应用约束和资料截止日期，系统完成研究范围整理、问题拆解、搜索阅读、证据收集、缺口判断、有限补搜和报告输出。最终报告以中文展示：问题与约束、方案对比、建议与理由、局限及未知项、引用与来源。

代表性任务：为一个小型企业知识库选择 BM25、向量检索或混合检索方案；比较单 Agent、Supervisor-Workers 和固定 Workflow 对可靠性的影响；比较不同会话恢复方案。示例只用于定义功能，不预设研究结论。

每个关键事实要绑定实际获取的来源和原文片段。被检索到的网页不是已核实的证据；URL 可打开也不代表它支持结论。缺少证据、来源互相冲突或内容已过期时，报告应明确表达这种限制。

## 开源选型

核查日期：2026-10-14。以 GitHub 元数据、README 和实际源代码为依据，维护状态不等同于质量保证。

| 项目 | 核实到的情况 | 本项目用途 |
|---|---|---|
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | Python 项目，Apache-2.0，未归档；支持网页/本地资料研究、来源收集、报告生成、多 Agent；README 当前要求 Python 3.12+ | 主底座，复用检索、抓取、上下文收集与基础报告功能 |
| [Deep Research From Scratch](https://github.com/langchain-ai/deep_research_from_scratch) | LangChain 官方课程代码，MIT，未归档；展示 Scope、Research、Write、Supervisor 和研究子图 | 阅读与架构参考，供用户理解研究循环，不作为第二套运行引擎 |
| [Open Deep Research](https://github.com/langchain-ai/open_deep_research) | MIT；GitHub 显示已于 2026-08-21 归档；有模型/搜索配置、研究图和评测示例 | 固定版本学习和流程参考，避免把它描述为持续维护的主依赖 |
| [DeerFlow](https://github.com/bytedance/deer-flow) | MIT，未归档；2.0 为通用 SuperAgent harness；旧研究框架位于实际链接指向的 main-1.x 分支 | 参考进度界面和任务组织，不引入整个平台 |
| [Tongyi DeepResearch](https://github.com/Alibaba-NLP/DeepResearch) | Apache-2.0，未归档；含 30B-A3B 模型与推理流程，也支持 API 方式 | 后续模型/研究策略实验参考，首版不部署大模型或复现训练 |

主底座已核查提交：`assafelovic/gpt-researcher@3582a6841fe7dc801e2a34e34ee408641aea9bce`。实际执行时先用此提交建立版本锁；如发现依赖无法解析，通过明确的兼容性修复提交解决，记录原因，不静默更新上游。

实际读取的 SDK 文件是 `gpt_researcher/agent.py`。确认存在：`conduct_research()`、`write_report()`、`get_research_sources()`、`get_costs()`；构造器支持 `config_path`、`source_urls`、`query_domains`、`context` 和 `log_handler`。适配器只引用这一版本支持的接口；初始化与集成时仍要验证返回数据结构。

## 实现选择

以下是 Codex 的建议，并非用户逐项指定的技术偏好。

- 新项目目录：`E:/codeproject/deepresearch-agent`。不改现有采购、SWE 或 OpenHands 项目。
- Python 3.12+、GPT Researcher、FastAPI、Pydantic、SQLite、pytest。首版使用简单 HTML/JavaScript 页面和轮询；界面稳定后再按实际需要增加 SSE。
- GPT Researcher 保留为基线和研究步骤引擎；通过适配器封装，领域逻辑、证据、状态及评测在自己的模块中实现。必要的上游修复要单独记录。
- 模型与搜索提供方可配置。先验证一套用户可用的模型接口与搜索接口，不假定普通聊天模型自动支持所有结构化输出。API 凭据仅配置在本地环境文件中。
- 未配置 API 时只能运行标注清楚的离线回放与测试，不能把回放报告声称为真实联网成果。
- 第一版在本机单进程运行，SQLite WAL 支持单工作进程写入。Docker 打包作为交付准备；公网部署、账号系统和多租户不在首版范围。

## 工作流与边界

范围整理 → 研究计划 → 有界研究 → 证据核验 → 信息缺口检查 → 有限补搜 → 报告 → 最终结构校验。

运行参数默认：最多 3 轮；每轮最多 3 个研究子问题；外层并发度 2；总研究调用上限 8；单个 SDK 研究步骤超时 180 秒；SDK 调用失败不自动重试，用户可选择恢复。第三轮后不得继续循环。总调用上限限制外层子任务数量，不宣称等于底座内部 HTTP 或模型调用数量。

SDK 内部并发、深度及超时也要通过经核实的配置约束，并在集成测试中检查；若底座无法稳定接受这些约束，要减小运行范围或实现明确的最小补丁。模型与搜索实际费用未知时只展示供应商用量/SDK估算以及“费用未完整统计”，不能填写零元。

首版实现轮次、调用数和超时预算。按货币金额的硬预算作为后续扩展，必须先有真实模型/搜索价目和调用前费用预留机制；首版不承诺严格金额上限。大批量在线评测需先确定实际费用范围。

信息缺口判断区分：已覆盖、缺少证据、存在冲突、不适用。补搜只针对缺少证据或冲突且预算允许的项目。达到预算上限或材料不足时输出带限制的报告。

官方文档、仓库及论文应优先；社区文章可补充经验，但不能被重新标为官方结论。来源类型标注与可信度判断分开，论文观点也不自动等于事实。抓取时间、网页发布日期、所述产品版本分别记录；抓取时间不能替代发布日期。无法确定日期时标为未知。

`as_of` 的首版语义是尽力遵守并披露限制，不提供严格的历史网页快照重建。已知发布日期晚于截止日的内容不能用于声称“截至该日”的事实，可另列为截止日后补充；无日期或当前文档覆盖旧版本时标为时间适用性未核实，不能声称还原了历史状态。要求严格历史事实的任务返回该能力范围的限制。此选择由 Codex 为缩小首版范围作出。

## 数据契约

所有模型放在 `src/deepresearch_app/models.py`，采用 Pydantic；日期时间为带时区的 ISO 8601，默认显示 Asia/Shanghai。

- `ResearchRequest`：`topic: str`、`constraints: dict[str, str]`、`as_of: date`、`max_rounds: int=3`、`max_calls: int=8`。主题去空白后 1–2000 字；轮数范围 1–3，调用上限 1–8。
- `ResearchPlan`：`questions: list[str]`，最多 3 个问题；`required_dimensions: list[str]`。
- `Source`：`id: str`、`url: str`、`title: str`、`text: str`、`retrieved_at: datetime`、`published_at: date|None`、`source_type: str`、`content_hash: str`、`time_status: Literal['within_cutoff','after_cutoff','unknown']`。只有读取到非空正文的来源可成为有效证据。
- `Evidence`：`id: str`、`source_id: str`、`quote: str`、`claim: str`、`verdict: Literal['supported','contradicted','uncertain']`、`reason: str`。原文片段必须是来源正文中规范化空白后的子串；语义支持要单独判断，不能由子串校验代替。
- `ResearchPacket`：`context: str`、`sources: list[Source]`、`usage: dict[str, int|float|bool|None]`、`duration_ms: int`。SDK 上下文无论是字符串还是列表，适配器统一转为字符串；布尔值用于费用统计完整性标记。
- `GapDecision`：`complete: bool`、`followups: list[str]`、`reason: str`，下一轮最多 3 个问题。
- `ReportClaim`：`id: str`、`text: str`、`kind: Literal['fact','recommendation','uncertainty']`、`evidence_ids: list[str]`。
- `ComparisonRow`：`label: str`、`aspects: dict[str,list[str]]`，表格单元格存 claim ID，不存额外自由结论。
- `ResearchReport`：`title: str`、`summary_claim_ids: list[str]`、`comparison: list[ComparisonRow]`、`claims: list[ReportClaim]`、`limitation_claim_ids: list[str]`。摘要、对比表、理由和局限全部从同一个 claims 账本渲染；除固定标题、列名和输入问题之外，不允许另一条未经校验的自由文本输出路径。先生成结构化报告，再由确定性渲染器生成 Markdown；禁止模型直接构造未经验证的引用 URL。
- `ReportValidation`：`valid: bool`、`errors: list[str]`。事实性 claim 要引用至少一条 supported 证据；建议必须标为建议。失败时允许一次结构修复，仍失败则保存草稿与错误并将任务标为 failed，不把草稿当已验证报告发布。
- `ResearchState`：`run_id: str`、`request: ResearchRequest`、`plan: ResearchPlan|None`、`stage: str`、`round: int`、`calls: int`、`completed_steps: dict[str,ResearchPacket]`、`sources: list[Source]`、`evidence: list[Evidence]`、`gap: GapDecision|None`、`report: ResearchReport|None`、`status: str`、`warnings: list[str]`。

## 持久化和恢复

SQLite 表包括 runs、steps、sources、evidence、events；每次成功 SDK 调用完成后保存 packet，再推进状态。证据与报告也保存后再推进状态。步骤键为 `run_id:round:question_index`，运行内唯一；并发 worker 不能各自覆盖一份全局 JSON，写入由单工作进程的存储层串行事务完成。

恢复跳过已保存 completed packet 的步骤；失败或运行中断的步骤允许重新执行。崩溃发生在供应商调用完成与本地结果保存之间时，可能重复调用并产生额外费用；第一版只承诺已保存步骤不重复，不承诺外部调用 exactly-once。恢复本身也遵守剩余轮次和调用预算，调用计数在外部调用前持久化预留。

事件包含单调递增序号、阶段、步骤、状态和耗时。轮询接口支持 `after_seq`；用户可以刷新页面继续查看同一任务。刷新页面不是取消任务。单机进程重启后不自动执行未完成任务，用户显式选择恢复。

## 用户验收界面

一个页面提供：研究问题及约束输入、创建任务、阶段与错误显示、来源列表、原文片段、研究报告、未核实项、耗时/用量、恢复按钮、Markdown 和 JSON 下载。

任务 API：`POST /api/research` 返回 202 和 run_id；`GET /api/research/{run_id}`；`GET /api/research/{run_id}/events?after_seq=0`；`POST /api/research/{run_id}/resume`；`GET /api/research/{run_id}/report?format=markdown|json`。运行中或已完成任务再次 resume 返回 409。报告无有效完成版本时下载返回 409；草稿可在任务详情里看，状态要清楚。

首版只监听 `127.0.0.1`。来源抓取应拒绝 file URL、localhost 和私有网络地址，防止普通研究请求误访问本地服务；这是联网读取模块的必要行为，不扩展为安全审计项目。

## 评测设计

先准备 10 个开发题和 20 个留出题，按主题族隔离，防止同一模板改词同时进入两份数据。用户评审问题、约束和必须覆盖的维度；这是项目私有验收集，不冒充公开 benchmark。

基线 A：固定主底座版本，使用基础研究与报告流程，保持默认工程能力，明确锁定模型与配置；增强版 B：增加领域范围约束、证据账本、缺口补搜与恢复。基线不为了输而删减能力。

策略对照使用冻结的来源正文和检索回放，A/B 面对相同候选材料、模型设置与外层预算；两者不同的取材路径和模型用量要保留。真实联网另做 5 个用户验收题，评估实际搜索、失败和时效，不把在线随机差异直接当成策略提升。

指标：

1. 维度覆盖率：有正确且有支持依据的回答维度 / 人工标注的应回答维度。
2. 引用支持率：抽查的事实 claim 中，被其引用原文实际支持的数量 / 抽查事实 claim 数量。来源可达率和原文片段存在率分别统计，不能替代此指标。
3. 未核实结论率：无有效支持却写成确定事实的 claim / 全部事实 claim。
4. 用户盲评：实用性、清晰度、约束贴合度各 1–5 分，隐藏 A/B 标签并随机呈现；模型裁判只能做辅助标签，不能独立证明正确性。
5. 工程指标：固定故障注入下恢复成功率、已保存步骤的重复调用数、完成率、实际耗时、token 用量及可核算费用。

没有预设提升百分比；结果无提升也应保留和解释。开发题可用于修改；留出集一次定稿后封存，若根据留出结果改策略必须新增独立验收题。

## 交付阶段

| 阶段 | Codex 交付 | 用户评估 |
|---|---|---|
| 1 基础原型 | 锁定底座、配置检查、离线测试和一条真实研究链路 | 给 3 个真实问题，检查输出是否对需求有用 |
| 2 可追溯报告 | 来源正文、证据片段、结构化报告和引用检查 | 点击核对关键事实，标记 unsupported / 冲突 |
| 3 深度研究 | 缺口判断、有限补搜、预算和状态恢复 | 测试约束遗漏、资料不足、超时与恢复 |
| 4 产品演示 | 本机页面、进度、来源、报告、恢复和导出 | 自行提交新问题并完成端到端操作 |
| 5 评测与项目材料 | 10/20 题分割、A/B 结果、失败案例、Docker、架构及演示说明 | 盲评报告、确认结果与项目陈述 |

没有采用此前“每天 2–3 小时、4 周”的学习假设：用户已明确由 Codex 实现。各阶段按可验收交付推进；模型/搜索账号、网络、依赖和用户反馈影响实际完成时间，不预先承诺固定日期。

## 可由实现者决定的细节

提示词文案、函数内部实现、HTML 样式、数据库索引和配置组织由 Codex 决定，只要符合本文契约。第一版不做任意网页操作、模型训练、账号系统、复杂前端、PDF/Word 生成、定时监控或一组并行运行的开源平台。

真实联网前还需要用户可用的模型和搜索配置；用户不用将密钥贴到聊天。实现者可先完成不依赖这些配置的代码、回放、测试和文档。批量付费在线评测和公网部署需要单独确定具体范围。

## GitHub 维护与溯源

用户已要求每次改动配独立 Markdown 文档，并上传 GitHub 更新和备份；已确认目标为新建公开仓库 `luxleader/deepresearch-agent`。这是持续同步的授权，无须每次再问。用户已完成一次空仓库创建，GitHub 元数据已核实公开状态、main 默认分支和连接的写入权限。后续通过 GitHub 连接写入并回读核验；本机 Git 登录未配置时不妨碍连接上传。不能将待上传写成已备份。

每个逻辑改动采用一个变更 ID，例如 `DR-20261014-001`，独立文档放在 `docs/changes/2026-10-14-001-project-planning.md`。文档记录需求来源、文件、具体决策、核验命令与结果、风险和回退方法。每个 Git commit 消息含同一变更 ID，因此不在提交前文档中臆造尚不存在的当前 commit SHA。

文档、代码和对应验证应同批提交；后续发现的问题另开变更文档和提交，不覆盖旧的决策记录。允许补充纯粹笔误修正，但也记录实际变化。发布或推送失败不丢弃本地提交，报告实际同步状态，修复后使用 fast-forward 或基于最新远端的合并，禁止未经请求重写历史。不要上传 `.env`、密钥、虚拟环境、运行数据库、完整会话日志或简历。

保留 `docs/upstream.md` 记录所有复用来源、固定提交、许可证、修改清单；项目贡献说明区分上游能力、本项目实现和用户需求/评审验收贡献。里程碑发布使用有说明的版本标签。每次同步后核对远端 SHA 和文件，而不只依赖“调用成功”。

只读设计审阅指出两点，并已纳入本版：全报告文字经 claims 账本统一校验；资料截止日期采用上述尽力遵守并显式披露限制的语义。

## 参考来源

- https://github.com/assafelovic/gpt-researcher
- https://github.com/assafelovic/gpt-researcher/blob/3582a6841fe7dc801e2a34e34ee408641aea9bce/gpt_researcher/agent.py
- https://docs.gptr.dev/docs/gpt-researcher/gptr/pip-package
- https://github.com/langchain-ai/deep_research_from_scratch
- https://github.com/langchain-ai/open_deep_research
- https://github.com/bytedance/deer-flow
- https://github.com/Alibaba-NLP/DeepResearch
