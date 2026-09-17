# prism2api

**0.1.1 · 离线核心已验证，真实 Prism transport 尚未实现／验证。**

独立 Python SDK 与仅本机开放的文本 API。默认 `unconfigured`：模型列表为空，真实生成请求拒绝；只有显式 `--mock` 才启用合成测试，不把模拟响应包装成 Prism 回答。

## 安装和验证

支持范围：Python ≥3.12，POSIX（macOS/Linux）。本次实际验证 Linux/Python 3.13.5；macOS 与 Python 3.12 留作本地矩阵验证。Windows 暂不支持运行目录锁。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m prism2api smoke --mock --home /tmp/prism2api-offline-smoke
```

完整运行时状态应放在仓库外。测试使用临时目录、合成数据及断网守卫；仅一个标为 `loopback` 的测试允许本机 HTTP，不允许访问 Prism。

## 本机服务

```bash
.venv/bin/python -m prism2api serve --mock --home "$HOME/.prism2api-mock" --port 8765
```

启动后在 `$HOME/.prism2api-mock/credentials/gateway.key` 生成随机调用方密钥；也可显式配置 `PRISM2API_KEY`。不把 key 输出进日志或提交进仓库。删除 `--mock` 后，未配置真实 transport 时服务不提供生成能力。

已实现：原生任务提交／查询／结果／取消意图／只读核对；单条 user 文本、非流式的 `/v1/chat/completions` 子集；嵌入式和 daemon SDK。未知参数、tools、多轮消息、流式请求均明确拒绝。模型别名 `prism-default` **不是已证实的上游模型身份**；未知用量与模型确认值保持 null／省略。

## 接入真实 Prism

按照 [本地对接指南](docs/guides/gemini-local-integration.md) 实现一个经真实证据验证的 `BaseTransport` 子类，以可信的本地 `module:factory(settings)` 装配：

```bash
.venv/bin/python -m prism2api serve \
  --transport-factory prism2api.transport.prism_web:create_transport \
  --home "$HOME/.prism2api-live" --port 8765
```

**`prism_web` 当前仅为未接入真实抓包证据的草案骨架（unverified scaffold），能力全数保持 UNKNOWN + DISABLED 且拒绝提交生成。必须在收集 A 级真实抓包证据后方可实现生产协议。** 不得把截图中的候选 URL、模型名称或额度说法当成已验证协议。仅在本人获授权、适用条款允许的范围验证；不绕过限流或账号安全检查。

## 状态与设计

- [本次完成项、验证证据与明确边界](docs/validation/offline-runtime-asf.md)
- [运行时／transport 接口合同](docs/guides/transport-handoff.md)
- [原架构总书](docs/architecture/00-master-design-book.md)
- [项目 Overlay](Agent-init/PROJECT_OVERLAY.md)
- [本次 OpenSpec change](openspec/changes/archive/2026-09-16-complete-offline-core-asf/proposal.md)

本版不是架构书全部 52 项的产品验收。尚无真实 Prism 登录、网络协议、浏览器自动化、SSE、通用工具调用、多模态、多账号、自动清理远端项目或生产部署保证。运行中缺少结局会进入 `uncertain` 并停止新生成；必须查清旧任务，而不是清库、换运行目录或重发来绕过它。
