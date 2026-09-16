# 项目 Overlay — prism2api

> 补丁阶段状态，2026-09-16。基线 `59aad2f`；本补丁依据用户“直接做完，Gemini 只做本地对接”的授权补齐离线核心。**GitHub main 未因本包而改变**，接手先核 `git status`、`git rev-parse HEAD` 与实际文件。沿用 dev-flow-GPT 路线，不安装旧 Claude IPC/hook。

## 0. 项目身份

Python ≥3.12，发行版本 0.1.1。CLI=`python -m prism2api`，包配置=`pyproject.toml`。运行目标 POSIX，本轮实测 Linux/Python 3.13.5。默认 transport 未配置；mock 必须显式选择。真实 Prism 协议未验证。

## 1. 代码入口地图

| 面 | 位置 |
|---|---|
| CLI、SDK、HTTP | `src/prism2api/__main__.py`、`client.py`、`api/app.py` |
| 唯一执行者／恢复／幂等 | `runtime/supervisor.py` |
| 输入冻结／事务／证据 | `storage/db.py`、`storage/journal.py` |
| 终态与归属 | `runtime/events.py`、`provider/adapter.py` |
| 上下文／OS 锁 | `runtime/context.py`、`runtime/locking.py` |
| 上游边界 | `transport/base.py`、`unconfigured.py`、`mock_transport.py` |

## 2. 设计圣经

`docs/architecture/00-master-design-book.md` 与 A4 合同索引保留。下一阶段重点 M02/M03/M04/M05/M07；架构目标不等于当前能力。实际本地 transport 插槽合同见 `docs/guides/transport-handoff.md`。本次不重写架构书、不改变其长期安全边界。

## 3. 测试体系

```bash
python -m pytest -q
python -m pytest -q tests/test_terminal_contract.py tests/test_audit_regressions.py
python -m pytest -q tests/test_runtime_readiness.py
```

本次 103 passed 是附件所列版本下的运行证据，未来按真实命令更新，不能把计数当全部合同覆盖率。`tests/conftest.py` 默认封锁网络及外部 DNS，清除 ambient PRISM2API 环境变量；只有 loopback 标记允许本机 socket。真实账号调用不得进入默认测试。

## 4. Spec 工具

仓库已有 OpenSpec；本次新增 `openspec/changes/complete-offline-core-asf/`。本环境没有 OpenSpec CLI，未宣称 validate/archive 已执行。任务、设计、delta、验证正文完整提供；本地先 `openspec validate complete-offline-core-asf --strict`，验证通过后经用户确认归档，禁止直接修改 `openspec/specs/**` 或篡改历史归档。

## 5. 项目铁律

已接受输入不可在执行时替换；提交意图后不确定不重发；明确终态也要核对任务归属与冲突；没有可校验结果不能报成功；未知模型／用量不能编造；SDK 与 HTTP 共用同一运行目录写入者；精确资源归属；凭证／原始 HAR／真实论文不进仓库。

## 6. 写入边界

本次获批核心修复：生产代码、测试、pyproject、保护性 gitignore、README、Overlay、新 change 与验证／对接指南。下一阶段 Gemini 只实现基于证据的 live transport、对应解析测试和本地集成记录；若发现确需改共享核心合同，停下给出最小冲突证据，不批量重写已通过实现。

## 7. Git / Ops

GitHub connector 写分支返回 403；交付应用补丁，非远端提交。只在基线及触及文件校验通过后应用；不覆盖 WIP、不 reset/stash/force push、不 `git add -A`，merge main 仍须用户明确同意。

## 8. 外部研究

保留 `docs/research/prior-art-prb/` 与 A1。新抓包是取证，不是竞品 README；只将相关协议材料纳入本地研究。旧两个同名无关仓库已略过，不新增平台／计费后台。

## 9. 北极星

可信、隔离、可恢复的 Prism 接入。离线通过不等于联网通过；本地运行不等于不上云。不是额度绕过或多账号轮换工具。

## 10. 执行模型

用户本机当前使用 Gemini；不要求新增模型或改写角色矩阵。代码与审核依靠明确合同、测试、源文件证据，不依靠模型自报完成。

## 11. 当前事实入口

`git log/status`、本次 change 的 `verification.md`、`docs/validation/offline-runtime-asf.md`。原 active architecture plan 是历史设计排期，当前实施入口为本次完成记录与 Gemini 本地对接指南，不把旧“尚无代码”快照作为当前事实。

## 12. 工作流集成

沿用已有 GPT 工作流文件；不自动安装 custom agents、skills、hooks、全局规则或新模型。文档按需读取；本次“离线核心完成”不自动打开真实账号测试或整本架构未来功能。
