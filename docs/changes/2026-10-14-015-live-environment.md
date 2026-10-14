# DR-20261014-015 · 固定 SDK 安装与联网环境锁

## 需求与改动
网络恢复后安装固定版 GPT Researcher，生成 requirements-live.lock，锁定项目及 SDK 的传递依赖并保留跨平台标记。更新安装说明；增加实际 SDK 构造契约测试，核心离线 CI 缺少 SDK 时明确跳过。

## 验证
uv pip install 固定 Git 提交成功，SDK 版本 0.16.0。实际构造使用人工测试值，无模型/搜索请求；验证 keyword context、Qwen enable_thinking=false、兼容地址与 SafeBrowser 实例。uv pip compile pyproject.toml requirements-live.txt --python-version 3.12 --universal 成功。完整回归结果以后续最终记录为准。

## 限制与回退
实际 SDK 提示缺少可选 MCP 适配包，本项目 mcp_strategy=disabled，不使用此功能。构造验证不能证明搜索、网络抓取、模型输出和质量；仍需本机密钥及真实问题。Windows 已安装，Linux/macOS 仅完成依赖解析，未执行。回退用 revert；本机额外 SDK 包不会随 Git 回退自动卸载。

## 备份与溯源
签名提交同 ID，依赖锁仅含公开包与上游固定 URL，不含本机密钥、数据库或日志。上传后回读。
