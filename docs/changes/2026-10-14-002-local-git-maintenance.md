# DR-20261014-002 本地 Git 历史与传输配置

日期：2026-10-14。

## 需求来源

用户要求持续 GitHub 更新与备份，并做好代码维护和溯源。本地工作目录也需要保留与远端一致的提交历史。

## 改动

- 新增本记录，并加入 docs/changes/README.md 索引。
- 实施计划改用下一可用变更编号，避免与维护提交重复使用编号。
- 本地仓库 main 跟踪 origin/main；本仓库的 Git http.sslBackend 设为 openssl。此设置仅在本仓库 .git/config 生效，不修改用户的全局配置，不关闭 TLS 证书校验。
- 本地 Git 身份使用 GitHub 已核实账号 luxleader 的 noreply 地址，没有读取私人邮箱。

## 原因与实际核验

通过 GitHub 连接创建并推进 main 后，回读全部 9 个文件，逐一比较内容与 Git blob SHA；均与本地一致，main 当时的提交为 574f814d71056724d1aad429f97643d99e6f17a7。对应初始化提交为 582bf138caaccc8cfbc7e75f556e5849b6a7b6cb。

默认 Git fetch 在 Windows schannel 后端失败：SEC_E_NO_CREDENTIALS。读取配置确认系统 http.sslbackend=schannel，用户配置了本机 HTTP 代理。仅对一次 fetch 指定 -c http.sslBackend=openssl 后成功；因此给本仓库单独设置该后端，保持原代理与 TLS 校验。此结论只确认本机该传输路径可用，不把它推广为所有环境的根因。

执行命令：

```powershell
git -c http.sslBackend=openssl fetch origin main
git reset --mixed origin/main
git branch --set-upstream-to=origin/main main
git config http.sslBackend openssl
git diff --check
git status --short
git log -2 --oneline
```

第一次 fetch 使用连接/低速超时参数防止卡住。reset 仅更新此前空的本地 HEAD 和索引，没有覆盖工作文件；同步后 status 无差异，log 与两次远端提交相符。产品实现和联网研究仍未执行。

## 限制与回退

本机尚未配置用于 Git push 的登录凭据，因此本次与后续可继续通过 GitHub 连接上传，不能把公开 fetch 成功等同于 Git push 已获认证。撤销本地后端选择可运行 git config --unset http.sslBackend；远端维护文档更正使用新的提交，不重写历史。
