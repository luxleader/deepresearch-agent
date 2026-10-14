# 评测协议

开发集 10 题、留出集 20 题按主题族隔离；`evals/online.jsonl` 为另列的 5 个联网验收候选题，需用户确认真实约束。题目与协议目前尚未人工审核，没有质量提升数据。

## 三种运行

- synthetic：人工构造回放，只检查流程、保存结果与盲评文件；不使用真实模型和 SDK，不评价研究质量。
- frozen：先保存经过用户核对的 `ResearchPacket` 正文、URL、正文哈希及日期。基础版使用固定 GPTR 原生 `write_report(ext_context=...)`，增强版在相同材料上规划、核验、判断缺口和写作。两边来源清单必须一致。此实验评估写作与证据策略，不能证明实际检索能力提升。
- live：基础版执行固定 SDK 的研究与报告，增强版执行完整流程。两边使用相同模型配置，保存来源清单。联网来源可能漂移，两边内部调用预算也不同；单列资料获取、时效与失败情况，不宣传等 token 对比。

运行示例（先按 README 安装并设置 PYTHONPATH 或安装包）：

```powershell
python scripts/run_eval.py --mode synthetic --limit 2
python scripts/run_eval.py --mode frozen --corpus runtime/corpus.json --limit 2
python scripts/run_eval.py --mode live --split online --limit 5
```

结果保存在忽略的 runtime 下，包含模型配置摘要/哈希、上游提交、日期、预算、来源摘要、耗时与实际已知用量。完整正文不得自动上传。`blind-pairs.json` 只含题目、约束和 X/Y 报告；`private-mapping.json` 仅由组织评测的人保留。随机 seed 固定顺序，报告风格本身仍可能暴露方法，盲评并非绝对匿名。

## 人工标注

先逐条提取两边报告的确定性事实。基础版的自由 Markdown 由人工分割成 `ResearchReport` 的 claims；不要把模型自动分割结果当成真值。增强版已有 claims，也应检查是否将事实伪装成建议。为每个事实填 `fact_supported`，为每个引用事实填 `citation_supported`，均为人工布尔判断；逐项填 covered_dimensions，最后填写 1–5 分 blind_score。

`score_claims(report, labels)` 的 labels 格式如下；任一事实缺标注时相应总体率为 null，零分母为 null，不能当作满分或零失败。建议与未知项不进入确定性事实分母，误标为建议的事实要先人工更正。

```json
{"claims":{"c1":{"fact_supported":true,"citation_supported":true}},"required_dimensions":["成本","部署"],"covered_dimensions":["部署"],"blind_score":4}
```

主要指标：维度覆盖率、引用支持率、未经支持的确定性事实比例、盲评分；同时报告事实数、引用事实数、标注数、耗时与用量。GPTR 的估算费用可能不支持自定义模型价格，外层模型 token 单列，`cost_complete=false` 表示不完整；缺失 token/金额保留 null。

## 复现与失败

先在开发题调试，用户确认题目与标注协议后才以 `--approved-holdout` 执行留出题。记录冻结材料的来源获取时间与版本；无日期材料显示时间适用性未知。保存不支持的结论、来源冲突、空正文及失败调用，不能只选成功案例。当前离线回放结果只能证明软件流程运行，真实模型研究与用户评分均待接入后执行。
