# DR-20261014-016 · 统一 pytest 导入路径

## 需求与改动
远端 Linux CI 测试步骤失败。以同样的 pytest 控制台入口在本机复现 scripts.check_change_record 无法导入；此前 python -m pytest 自动包含 cwd，掩盖差异。在 pytest 配置显式加入项目根目录，与 src 一同加载。

## 验证
控制台入口维护用例先因 ModuleNotFoundError 失败；修改后需同时验证 pytest 与 python -m pytest 完整套件，结果在最终交付记录核对。远端 Actions 状态通过公开 API 读取，私有日志下载未使用。

## 限制与回退
路径配置不会验证真实联网能力。回退可 revert，但控制台 CI 会重新出现导入失败。本次自动审批拒绝从本机 Git 凭据存储提取令牌下载日志，操作未执行；通过本机相同入口完成诊断。

## 备份与溯源
独立签名提交同 ID，推送后核对对应 Actions 状态和远端文件。
