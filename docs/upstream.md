# 上游选型与来源

核查日期：2026-10-14。这里只记录已查询的开源基础与拟采用方式，不声称完成集成。

| 来源 | 许可与维护状态 | 使用选择 |
|---|---|---|
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | Apache-2.0，未归档，README 要求 Python 3.12+ | 主底座，固定 `3582a6841fe7dc801e2a34e34ee408641aea9bce` |
| [Deep Research From Scratch](https://github.com/langchain-ai/deep_research_from_scratch) | MIT，官方课程代码，未归档 | 研究循环和用户理解材料 |
| [Open Deep Research](https://github.com/langchain-ai/open_deep_research) | MIT，已于 2026-08-21 归档 | 固定版本参考，不作为持续维护主依赖 |
| [DeerFlow](https://github.com/bytedance/deer-flow) | MIT，未归档，2.0 为通用 Agent 平台，旧框架链接为 main-1.x | 进度/组织参考，首版不引入整个平台 |
| [Tongyi DeepResearch](https://github.com/Alibaba-NLP/DeepResearch) | Apache-2.0，30B-A3B 模型与推理流程，支持 API 使用 | 后续策略或模型研究，首版不训练/部署大模型 |

已读取 GPT Researcher README 和固定版本 gpt_researcher/agent.py，确认核心公开方法：conduct_research、write_report、get_research_sources、get_costs。实际集成仍需要验证 SDK 返回数据结构、配置和模型接口兼容性。

本项目代码尚未实现；上游检索/抓取/报告能力不计入本项目独立实现。将来复用代码时保留原许可证和必要声明，独立修改在改动文档中注明来源、固定版本及改动原因。
