# Direct HTTP fixed-context addendum · 0.2.0rc1

## 决议与边界

根据用户“手工 Cookie、发文本取回复，不继续浏览器研究”的范围，新增 `prism2api.direct`。这是一条显式固定上下文入口，不伪造旧 `ISOLATED_CONTEXT` / `TASK_LOOKUP` capability，也不把旧模型的八模块全部重写。

入口：`import-curl → bootstrap.json → DirectEngine → authenticated loopback API`。

`Bootstrap` 保留一条成功请求里的 Cookie、UA、全部 metadata（包括原始 JSON 类型的 `codex_listen_snapshot`）、上下文和输入模板。所有对象的默认 repr 和 CLI 状态不包含这些内容。导入完全校验成功才原子替换文件；既有 secret 配置不自动迁移，拒绝不同快照混拼。

`DirectEngine` 每个 home 一把 POSIX 进程锁、每进程一个异步执行锁。生成前 heartbeat 只做一次，不自动 provision。start 意图先持久化，HTTP start 没有重试。状态轮询保留上游返回的新 turn_state 值与类型，核对明确出现的远端身份字段；终态失败与缺终态分开。

`Journal` 独立存放在同一个私有 direct home，不与旧 Supervisor DB 共用。它只承载 fixed-chat 模式的本地 run、哈希、回执、结果和计数；opaque 回执可能敏感，因此数据库也为 0600。未决任务 across restart 保持 uncertain，阻止继续生成。不会把 local operation ID 当远端 ID。

浏览器无需被程序启动；bootstrap 的上游有效期、snapshot 的更新行为和特定环境的脱浏览器可用性，仍需真实本机验收。peer README 是协议线索，不等于本次 A 级测试。

## 协议借鉴

| 借鉴点 | 采用方式 | 不采用 |
|---|---|---|
| snapshot | 保留完整 metadata 和原 JSON 类型 | 省略未知字段／拼接其他项目 snapshot |
| heartbeat | 固定 Prism origin + 捕获的 sandbox token | 自动新建 sandbox 或绕过登录检查 |
| User-Agent | 同一 cURL 捕获值 | 随意固定一个桌面 UA |
| turn_state | 保存并回传最新的原始值 | 重构／伪造／自行签名 |
| 小型网关 | 一条 Chat Completions 子集 | 工具执行、所有 SDK 全兼容的宣传 |

## 开发与验收

新增代码合同测试、真实本机 TCP + 假上游集成、子进程崩溃恢复测试；保留旧 offline core 回归。所有这些均明确是离线测试。真实 smoke CLI 使用随机 nonce、停止于首个失败，只有实际内容匹配才通过。不得将测试数字写成代码覆盖率、将类初始化写成认证成功、将 HTTP 可达写成生成完成。

此 addendum 不修改历史 OpenSpec 归档或长期架构的 source of truth。代码/文档更新直接记录本 change；无需安装额外 agent/hook。
