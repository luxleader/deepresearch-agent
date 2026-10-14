# DR-20261014-010 · Qwen-Plus 非思考模式配置

## 需求与改动
用户选择 Qwen-Plus＋Tavily。新增 DR_PROVIDER=qwen，直接 JSON 请求设置 enable_thinking=false；SDK 的 LLM_KWARGS 使用兼容接口地址及 extra_body。更新 .env.example，密钥保持空值。

## 验证
新增请求契约测试先因缺失 enable_thinking 失败，实现后全套 43 passed、1 条上游弃用提示。模拟 HTTP 验证 JSON 参数、返回 schema 和 token 统计。核对官方千问 JSON 输出文档及 GPTR OpenAI provider 参数透传源码。

## 限制与回退
固定 SDK 尚未安装并完成真实请求，不能把模拟测试称为 Qwen 联网兼容性验证。控制台区域、账号空间和模型可用性需以用户账号为准；兼容接口地址可配置。回退用 revert 本提交。

## 备份与溯源
提交包含本 ID，常规 Git push 后回读核对。GitHub 直连间歇失败；先保留签名提交，成功与否以最终核对记录为准。
