# M07 认证、Transport、安全与本地部署

> v0.1.0 · draft。首版面向本机单使用者；云端模型计算与账号权限不归本地 gateway 控制。

## 1. 信任边界

```text
调用方 ──本地 API key──> gateway ──授权会话──> Prism
                             │
                             ├─ 专用本地凭证与运行目录
                             └─ 非受信的网页、模型文本、artifact
```

两个认证域分开：本地 API key 只授权调用网关；上游会话只授权访问对应账号。不得把上游 token 当本地 API key 直接转交客户端，也不得让客户端用 body 自报 principal。

## 2. `AuthProfile` 与登录流程

`AuthProfile` 保存本地 profile_id、账号范围引用、授权来源、credential_locator、状态、上次验证时间和可选 expiry 证据。凭证实体不进入 RunRecord、manifest 或 traceback。

建议流程是 operator 在专用环境中正常登录；网关只使用明确交给它的会话，不扫描其他浏览器、不自动复制日用 profile、不收集别人的凭证。不预先假设 Cookie 名称、认证路由或续期接口。

认证状态至少区分 `not_configured / ready / expired / intervention_required / quarantined`。账号登录失效时关闭相关能力准入并返回可操作诊断，不自动提交测试 prompt，也不换账号。

认证刷新只有在官方／上游正常授权流程可用且得到验证后才启用；不得把反复失败的刷新做成绕过访问控制的循环。验证码、2FA 或风险验证转为人工处理，不自动突破。

## 3. TransportSession 的归属

HTTP transport 与 browser-assisted transport 各自拥有连接资源，二者通过 M02 合同提供能力。首轮只实现 P0 选中的一种，不无证据做自动 fallback。

browser-assisted 的 `TransportSession` 绑定 auth_profile、独立 browser generation、受控 context 和自有 pages。lease 携带 generation，浏览器重启后旧 lease 失效；即使新页面 URL 一样，也不能接受旧 callback 写入新 run。

不连接用户日用 Chrome profile 来省事，不远程暴露调试端口，不在日志回显含会话秘密的 DevTools 地址。若未来采用外部已运行浏览器，必须另有清晰的资源所有权及精确 target 合同。

## 4. 本地服务安全基线

| 边界 | 首版设计 |
|---|---|
| 网络监听 | 只允许 loopback；非 loopback 配置拒绝启动，而非仅警告 |
| API 鉴权 | 原生／兼容接口必须验证本地 key；健康检查仅最少状态 |
| Host / Origin | 有明确允许列表，防止 DNS rebinding／恶意网页误用；CORS 默认关闭 |
| 请求预算 | body、消息数、队列、结果大小、事件数与时限均校验；超限显式失败 |
| 敏感文件 | POSIX 目录 0700、凭证 0600，禁止写入仓库与外部同步路径；跨平台实现另测 |
| 出站目标 | 仅经授权研究确认的上游 origin；重定向重新校验，不转发到任意 host |
| 调试与错误 | 不回显 Authorization、Cookie、完整请求、账户邮箱、原始上游错误页 |
| 模型产物 | 视为非受信数据；不执行命令、不自动解析成控制配置 |
| 文件/URL 输入 | 首版不支持任意上传与下载；artifact URL 不自动 fetch，避免 SSRF 与越权 |

loopback 不是绝对可信环境，因此 key、Host、Origin 与路径验证仍保留。网页内容或参考仓库中的指令不能改变本地安全配置与执行权限。

## 5. 启动、关闭与资源限额

启动次序：校验显式配置与权限 → 获取运行目录排他 OS 锁 → 打开 Journal／检查 schema → 恢复在途任务与账号 latch → 初始化所需 transport → 读取能力证据 → 计算 readiness。不能为使 ready 变绿而自动提交模型测试。

关闭次序：停止新准入 → 给已有任务规定的排空窗口 → 保存取消／不确定状态 → 有界清理 callbacks、连接和自有页面 → 关闭存储。不是直接 kill 浏览器后统一把任务标 cancelled。

首版仅一个 server worker，禁止用多个 Uvicorn workers 或多个 embedded 实例共享目录运行。OS 锁实现要用真实互斥机制，不能只检查锁文件是否存在，也不根据 PID 文本就认定过期。

限流与冷却状态尊重上游实际返回，支持本地 backpressure，但不做账号轮换或代理切换。配额信息未知就展示未知，不从“目前能发”推导剩余额度。

## 6. 技术选型与依赖边界

**建议而非已安装状态**：Python 3.12 作为首轮基线；标准库 `sqlite3` 支撑 Journal；FastAPI/Pydantic 支撑本地 API 与校验；HTTP 路线考虑 httpx；浏览器路线考虑 Playwright；pytest 支撑确定性测试。具体版本应在选定 transport 的实现 change 中锁定并验证。

依赖按用途拆分：core 不因 HTTP server 就强制启动浏览器；browser extra 不因安装就读取个人 profile；测试 extra 不包含真实认证材料。暂不加入 ORM、Redis、Camoufox、Prometheus 或分布式队列，除非出现可验证需求。

参考仓库的许可证只约束其代码，不给 Prism 服务授权；仓库许可证与依赖许可证分别核对。本包不复制第三方运行时源码、不选定项目软件许可证。

## 7. 故障诊断

区分本地 key 错误、上游登录失效、账号资格、能力未验证、协议漂移、队列耗尽、上下文 busy、生成不确定、结果完整性错误。不要把所有问题返回“网络错误，重试即可”。

诊断先读本地状态、版本、证据与 run；下一步动作必须指向精确问题，例如“手工重新登录该 auth profile”或“核对 run 的远端任务”。未经许可不为诊断上传日志或向第三方发送凭证。

## 8. 借鉴、验收与未决

AIstudioProxyAPI 的浏览器操作与服务启动分层可参考；Gemini-API 的凭证生命周期只作思路，不采用其具体 Cookie；grok2api 的账号／网关功能规模不进入首版。[R2](../../research/prior-art-prb/sources.md#r2) [R3](../../research/prior-art-prb/sources.md#r3) [R4](../../research/prior-art-prb/sources.md#r4)

`T41` loopback／鉴权／Host-Origin 边界；`T42` 登录失效不生成也不轮号；`T43` 专用 profile 与 generation 失效；`T44` 第二进程不启动 worker；`T45` 超时和资源预算；`T46` 产物／URL 不能越权出站或执行；`T47` 关闭与重启不清洗 uncertain。

未决 `U03` 认证、`U12` 授权／访问资格、`U14` 预算、`U15` 选型／版本与许可证，见 [A2](../appendices/a2-evidence-and-open-questions.md)。
