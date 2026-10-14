# DR-20261014-004 数据契约与研究底座

## 需求来源
实现用户确认的基础原型、来源追踪和固定 GPT Researcher 基础。

## 改动
新增 Pydantic 契约、配置、可替换接口、固定 SDK 适配、JSON 模型客户端、网页/PDF 安全读取与依赖锁。live SDK 独立 requirements-live.txt 固定上游提交；核心 uv.lock 锁定 29 个包。来源采用 URL＋正文哈希，正文为空不能成为证据；费用统计不完整明确标记。

## 决策
使用 SDK 的实例 scraper_manager.browse_urls 接口替换读取器，逐次验证重定向和公开地址、固定实际连接 IP，禁用模型生成图片/MCP。底座内部深度/并发限制与外层预算分开统计。Windows 增加 tzdata；PDF 最多读取前 20 页，暂无 OCR。

## 实际验证
先运行 tests/test_contracts_backend.py，因实现不存在出现 ModuleNotFoundError；实现后运行 pytest：13 passed。ruff check src tests：All checks passed。uv lock：Resolved 29 packages。测试使用真实契约/URL校验，外部 SDK 以已核实接口的测试替身隔离。

## 限制与回退
未安装/运行完整联网 SDK，未配置模型与搜索凭据，联网兼容性不能声称已验证。GitHub 连接与 HTTPS 推送当前失败，保留本地签名提交，稍后重试同步。撤回使用 revert。
