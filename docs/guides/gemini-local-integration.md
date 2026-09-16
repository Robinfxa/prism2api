# 给 Gemini：只做本机真实对接

## 目标与停点

ChatGPT 已完成基于 `59aad2f` 的离线核心修复与测试。你的目标是应用校验过的补丁、验证本机环境，然后用本人获授权会话实现真实 Prism transport。**不是再次自由修复全部核心、重写架构或批量生成新模块。** 不做后台、账号池、计费、SSE 或完整 tools。

## 1. 应用前先保留用户工作

先执行 `git status --short` 和 `git rev-parse HEAD`。补丁包外部 `apply_patch.py` 要求 HEAD=`59aad2f182232be41577a9e29adb7fe35d148776` 且目标干净。先读脚本，再运行：

```bash
python3 /path/to/prism2api-offline-core-0.1.1/apply_patch.py --repo /path/to/prism2api --check
python3 /path/to/prism2api-offline-core-0.1.1/apply_patch.py --repo /path/to/prism2api --apply
```

不会自动建分支、提交、push、stash、reset 或 merge。可先在正确基线上创建本地工作分支。已有新提交或 WIP 时停止应用，报告差异；不要强制覆盖，不要编辑包 manifest 来绕过检查。包中的 `changes/` 是备查文件，不要覆盖式复制整棵目录。

## 2. 本机离线验收

确认 Python ≥3.12；不擅自替换系统 Python。新建项目虚拟环境并安装 `.[dev]`，运行 `python -m pytest -q`。交付基线为 103 passed；目标为真实测试通过，不是机械凑计数。本次外部环境实测 Python 3.13.5，需在用户 macOS 和实际 Python 版本复验。

用独立 mock home 执行 `python -m prism2api smoke --mock --home <仓库外临时目录>`，确认 transport_kind=mock、模型确认与 usage 为 null。默认不加 --mock 时不能偷偷返回模拟生成。

当前 OpenSpec CLI 未在交付环境运行。若本机已有：`openspec validate complete-offline-core-asf --strict`；先核本次 verification 和真实日志，再由用户确认归档，禁止改写历史 archive。若工具不存在，记录 blocked，不写“validate passed”。

## 3. 真实证据先行

必读：本指南、`transport-handoff.md`、M02/M03/M04/M05/M07 相关段。用专用浏览器 profile 与独立 scratch 项目；本人手动登录，不索取或上传聊天中的 session/cookie。不碰真实论文、共享项目或日用浏览器。

截图只提供两个候选路径（**未在本包证实**）：

```text
/api/llm/response_with_tools_start
/api/llm/response_with_tools_status
```

两者不能混写。不能据此编造 request body、Cookie 名、header、task 字段、模型身份、额度或无限调用保证。记录一次正常网页任务的请求链、输入、远端归属、正文、真正终态、超时与失败行为。至少一个独立后续请求复现已观察行为；不要用大量请求压测。

保存原始材料到仓库外私人路径。提交前人工检查脱敏版本，包括 URL/query/body/response/cookie/token/邮箱/项目名；规范 fixture 留稳定假 ID、来源时间、操作、解析版本，不留真实凭证。未拿到材料就明确缺口，不 mock 一份然后叫“真实抓包”。

## 4. 只新增实际 transport 与其解析测试

优先落位 `src/prism2api/transport/prism_web.py`（当前不存在）。返回 BaseTransport 子类，由可信本地 factory 装配，不改默认 unconfigured。

实现 prepare、单次 submit、observe、真实可支持的 read-only lookup。无法证明的能力保持 disabled；不能让默认 mock 的 VERIFIED 状态混入 live。可以先独立 probe 得到事实，再接 adapter；不使用有未知副作用的浏览器自动化兜底。

读 `transport-handoff.md` 的方法表：输入、上下文、句柄、timeout 和规范事件归属必须一致。HTTP 库不要在 POST 超时或401后自动重新提交生成。必须能把一次已经发出的任务标为 uncertain，并核查同一任务；没有真实查询能力就停在显式限制，而不是伪造恢复成功。

单元测试只 mock 真正外部 HTTP 边界，使用脱敏抓包样本，不 mock RunSupervisor/EventNormalizer 本体。遇到当前接口无法表达实际协议时，仅提交差异、受影响测试和最小改动建议，别顺手重构已通过的核心。

## 5. 本地集成成功线

- 本人会话与能力证据可核对，默认未配置仍拒绝生成。
- SDK 和 HTTP 文本子集可拿到真实正文、归属和终态；不依赖模型自报身份。
- 同幂等键重查／客户端重连不增加生成提交次数。
- 真实断线或无法确认结局时不报 succeeded，也不自行重发。
- 真实项目隔离验证通过，或明确不能支持 isolated 并关闭该能力；不能只比较两个本地字符串。
- 只有明确请求取消并收到真实确认才标 cancelled。
- 原 103 项离线测试保持通过，新 parser fixture 测试通过；live 测试必须显式 opt-in，独立记录，不进普通 pytest 默认集。

## 6. 最后回传什么

回传当前 commit/diff、改动文件、测试命令及原始摘要、真实已证实能力与仍未知项、一例去敏输入→句柄→终态→结果证据链。区分 offline passed / local HTTP passed / Prism live passed。GitHub commit/push/merge 权限按用户实际授权，不自动 merge。

若 Prism 不允许当前访问、认证遇安全验证、权限／条款不允许、限流、无法取得终态或精确任务归属：停止该在线动作，记录限制，不尝试绕过。架构与运行核心仍可保留，但不要把 live gate 标完成。
