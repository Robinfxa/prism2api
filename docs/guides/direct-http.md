# prism2api Direct HTTP · 0.2.0rc1

这是面向**个人固定会话**的纯 HTTP 实现交付版。程序不启动浏览器、不读取浏览器数据库、不从历史聊天寻找凭据，也不自动创建项目或 sandbox。浏览器仅由你本人用于登录、准备一个能正常回答的 Chat，以及复制该次成功请求的 cURL。

**验证状态：本版本经过离线合同测试和本机 TCP API 测试；本次交付没有使用真实 Prism 凭据、没有发送真实 Prism 请求。不能据此宣称已解决所有 sandbox 401/同步问题或提供长期稳定性保证。**

## 1. 安装

现有仓库合入本包后：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m prism2api.direct --help
```

也可以不修改仓库，安装交付包里的独立 wheel（Python 3.12 或更新版本）：

```bash
python3 -m venv .venv-direct
.venv-direct/bin/python -m pip install /path/to/prism2api_direct-0.2.0rc1-py3-none-any.whl
```

独立发行包命令是 `prism2api-direct`，模块入口是 `python -m prism2api.direct`。合入原仓库后，`python -m prism2api serve-http` 也会转到同一个实现。旧 `serve`、`serve-browser`、离线 SDK 不会被删除，也不用于本版 Direct 路径。

## 2. 一次性导入当前成功请求

先在本人授权的 Prism 项目中让网页实际完成一条简单回答。在 DevTools Network 中选择该次 `response_with_tools_start`，使用 **Copy as cURL (bash)**。不要把内容贴到聊天、GitHub issue、shell 命令行参数或截图。

macOS 剪贴板可直接管道导入：

```bash
pbpaste | .venv-direct/bin/python -m prism2api.direct import-curl
```

仓库虚拟环境则将 `.venv-direct/bin/python` 换成 `.venv/bin/python`。导入成功后清理剪贴板，避免同步到其他设备；原始 cURL 不由本程序保存。

文件模式也支持，但文件须属于当前用户、权限 0600，并位于仓库外：

```bash
.venv-direct/bin/python -m prism2api.direct import-curl --file /private/local/capture.curl
```

只接受**一条**指向 Prism start 端点的 POST。该工具是文本解析器，不执行 cURL/shell，不读取 `@file`，不接受 proxy、config、redirect、retry、TLS 关闭等 cURL 选项。无效输入不覆盖上一次成功导入。

本版本要求该请求包含 Cookie、User-Agent、project/user/conversation、sandbox URL/token，以及 `codex_listen_snapshot`。这是此实现采用的、来自同行研究的 HTTP bootstrap 条件，不是对 Prism 所有版本的普遍断言。没有捕获到字段就报告 incomplete，不根据旧值补齐。

全部数据以单一原子文件存入：

```text
~/.prism2api/direct/bootstrap.json      0600，整份文件均视为敏感
```

它保存完整 metadata、原始 snapshot 类型、必要请求头、完整 input 模板；仅清空最后一个 user message 的当前 text，调用时替换这一个字段。system/history 中可能含项目内容，所以 bootstrap **不只是 Cookie，也是私有内容**，不可上传。

不再拼接旧 `live-profile.json` 与手写 `fixed-context.json`。旧文件不读取、不修改。

## 3. 先确认一条，再开 API

```bash
# 纯本地格式检查，不联系上游
.venv-direct/bin/python -m prism2api.direct doctor-http --offline

# 可选：一次 sandbox heartbeat；成功也不等于 generation 已验证
.venv-direct/bin/python -m prism2api.direct doctor-http

# 真实、纯 HTTP 的单次调用。不要拿曾公开暴露的旧凭据测试。
.venv-direct/bin/python -m prism2api.direct probe-http \
  --prompt 'Reply exactly: PRISM_HTTP_CHECK' --timeout 180
```

只有返回的 `result.text` 等于预期，才是这一次真实生成成功。出现错误时先处理这一条，不循环发送十条尝试。

```bash
.venv-direct/bin/python -m prism2api.direct serve-http --port 8765 --timeout 180
```

服务只绑定 `127.0.0.1` 或 `::1`。认证密钥保存在 `~/.prism2api/direct/gateway.key`（0600），不打印。不可公网暴露或通过 tunnel 转发。

另一个终端：

```bash
.venv-direct/bin/python -m prism2api.direct smoke-http --count 3 --timeout 180
```

smoke 会发送随机精确回复请求，读取本地 run 的真实提交/轮询计数；首个失败就停止，未执行的项标记 not_run，不把单元测试或错误请求算成真实成功。

## 4. HTTP 使用

支持：

- `GET /healthz`：仅配置/忙闲/未决任务状态，不包含远端标识或凭据。
- `GET /v1/models`：仅本地别名 `prism-default`，不是模型身份确认。
- `POST /v1/chat/completions`：单条 user 文本，非流式，`n=1`。
- `GET /v1/runs/{local_run_id}`：认证后查看本地状态和调用次数。

除 healthz 外需要 `Authorization: Bearer <local gateway.key>`。固定项目/会话会保留上游上下文；同一时刻仅一条任务，忙时 409，不无限排队。服务拒绝多条 messages、tools、system/developer role、stream=true、未支持参数，不静默丢弃。

```python
from pathlib import Path
import httpx

home = Path.home() / '.prism2api' / 'direct'
key = (home / 'gateway.key').read_text().strip()
with httpx.Client(trust_env=False, timeout=190) as client:
    response = client.post(
        'http://127.0.0.1:8765/v1/chat/completions',
        headers={'Authorization': 'Bearer ' + key,
                 'Idempotency-Key': 'my-unique-logical-request-001'},
        json={'model': 'prism-default',
              'messages': [{'role': 'user', 'content': '用中文解释强化学习。'}]},
    )
    response.raise_for_status()
    print(response.json()['choices'][0]['message']['content'])
```

`Idempotency-Key` 相同且输入和导入批次一致时，不重复提交；已成功的结果可读缓存。不提供 upstream exactly-once 保证。

## 5. 出错后怎样处理

`upstream_unauthorized` / `sandbox_unauthorized`：上游或 sandbox 拒绝当前请求；可能与过期、撤销或不配套的 bootstrap 有关，但本程序不猜原因。回网页确认新请求能完成后，重新 Copy as cURL。停止 daemon 才能重新导入；不要手改 token 或拼接历史数据。

`sandbox_not_ready` / `sandbox_sync_timeout`：远端明确失败，返回错误而不是答案。不会调用 `/api/backend/1/new` 后自动再提交。

`uncertain`：已经可能发出 start，但结果不明。总 deadline 覆盖 heartbeat、submit、body read、polling 和等待，不会让一个 fetch 无限占住服务。该目录会阻止下一次 generation，跨进程重启也不清除。

```bash
# 停止 daemon 后，使用相同 --home
python -m prism2api.direct run-status --run run_...
python -m prism2api.direct reconcile-http --run run_...
```

reconcile 只对已有 request_id/turn_state 调 status，不 heartbeat、不创建资源、不重新 start。若缺回执，先在网页人工查清原任务。**仅在确认原任务已经停止后**才可：

```bash
python -m prism2api.direct acknowledge-run --run run_... --remote-stopped
```

这会留下 `abandoned / operator_confirmed_remote_stopped` 的人工记录，绝不伪装成服务器确认或成功。不能为了继续测试就随便使用这个开关。

## 6. 范围与来源

客户端不需要常驻浏览器，不等于已证明任何账号/任何 sandbox 状态下都能脱离网页生成。`codex_listen_snapshot`、heartbeat 及滚动 turn_state 的线索来自 `Danchuna/prismctl2api`；本版保存收到的字段而非猜字段，采用新的 Python 实现，保留无盲重试和未知用量语义。

本版不承诺自动登录、自动刷新凭据、隔离新项目、原生客户端工具、SSE、模型选择、token 用量、跨账号调度。浏览器实验模块仍是历史可选路径，不是本版依赖。

源码与测试用例不包含真实登录材料。不要把 bootstrap、数据库、raw HAR 或带凭据的 request/log 上传；即使文件在 repo 外，上传聊天或日志也仍然是泄露。
