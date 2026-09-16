# A3 阶段交付与验收矩阵

> v0.1.0 · draft。下列 **52 个 T 编号均是计划中的验收场景，不是本次运行过的测试**。本次实际文档验证另见 [报告](../../validation/architecture-book-prb-report.md)。

## 1. 阶段 gate

| 阶段 | 进入条件 | 必交付 | 离开条件 |
|---|---|---|---|
| 架构成书 | 用户要求已明确 | 总书、8 模块、5 附录、来源、Overlay、计划 | 文档一致性检查＋用户评审；当前尚未评审 |
| P0 协议证据 | 授权／资格确认，独立实验上下文 | 低风险真实任务、脱敏样本、协议说明、U 项更新 | 能区分提交／正文／终态／归属，并选出一种路线 |
| P1 核心客户端 | P0 证据与实现 artifact gate | native run、Journal、lease、单次 submit、结果查询 | 核心成功与崩溃／不确定路径可验证 |
| P2 本地 API | P1 通过，兼容映射与隔离有证据 | 原生 API＋受限 Chat Completions＋本地鉴权 | 公共请求进真 core、错误与参数不被吞掉 |
| P3 真流式与恢复 | delta／终态／cancel／lookup 能力明确 | 流完整性、断线、取消、重启、漂移处理 | 不重复、不伪 DONE、不盲重发、不串状态 |
| P4 客户端 qualification | 目标客户端与版本明确 | 实际请求 corpus 与正常／失败联调回执 | 逐客户端宣称范围；不做泛化“全部兼容” |

先后顺序不意味着把安全推迟到 P3：**提交账、所有权、凭证保护与诚实终态是 P1 起就必需的底线**。P3 扩展流式和更全面的恢复覆盖。

## 2. 确定性／live 验收清单

`offline` 表示未来通过真实 core 与边界 fake/replay 检查；`live` 表示需经授权的真实上游验证；`client` 表示真实调用方联调。含多个类型的条目需要分别给证据。

| ID | Owner | 可观察断言 | 验证面 |
|---|---|---|---|
| T01 | M01 | 无本地 API key 不发生排队或上游副作用 | offline |
| T02 | M01 | 未支持字段／角色在 submit 前明确失败 | offline |
| T03 | M01 | unknown/stale 模型能力不进入兼容模型表 | offline |
| T04 | M01 | principal B 无法查询／取消 A 的 run | offline |
| T05 | M01 | 完整历史一次投递，不与隐式旧会话重复叠加 | offline + live |
| T06 | M01 | SDK daemon/embedded 模式不能创建第二提交者 | offline |
| T07 | M02 | 缺依赖证据的 capability 无法启用 | offline |
| T08 | M02 | 请求 alias／UI 标签不直接成为 confirmed model | offline + live |
| T09 | M02 | adapter.submit 错误时不在内部自动重发 | offline |
| T10 | M02 | 未知关键事件使受影响能力隔离且停止新准入 | offline |
| T11 | M02 | UTF-8／协议语义跨帧解码不损伤事件 | offline + replay |
| T12 | M03 | 并发同 key、同 body 只有一个 run 和一次 submit | offline |
| T13 | M03 | 同 key、不同 body 返回冲突并保留原任务 | offline |
| T14 | M03 | intent 落账后崩溃，重启不自动第二次 submit | offline + recovery |
| T15 | M03 | 工作区创建结果未知时不重复创建掩盖故障 | offline |
| T16 | M03 | 客户端掉线仅影响 delivery/intent，不伪称远端取消 | offline + live |
| T17 | M03 | 完成／取消竞态按权威证据，不按最后回调覆盖 | offline + live |
| T18 | M03 | 旧 owner_epoch 回调不能改写新状态 | offline |
| T19 | M03 | 结果已过期的幂等重试不会补生成 | offline |
| T20 | M04 | 隔离请求 B 不接入 A 的受控项目／会话材料 | offline + live |
| T21 | M04 | explicit 只追加新 turn，revision 变更可被发现 | offline + live |
| T22 | M04 | lease 竞争失败者不关闭或撤销赢家资源 | offline |
| T23 | M04 | 人工导航／页面身份变化后旧 lease 不可继续写 | offline + live |
| T24 | M04 | 清理不关闭用户页面，不删除未授权远端项目 | offline + live |
| T25 | M04 | 没有强制只读证据时 capability 不宣传只读 | offline |
| T26 | M04 | 实验资源预算到达后停止创建而非广域清空 | offline |
| T27 | M05 | 上游网络片段与语义事件边界分离 | offline + replay |
| T28 | M05 | 累计快照只发真实增量，不重复正文 | offline |
| T29 | M05 | 已发正文非前缀改写时不伪造可修复追加流 | offline + replay |
| T30 | M05 | 慢 delivery 客户端不阻塞 ingestion | offline |
| T31 | M05 | ingestion overflow 显式损伤完整性，不丢片后成功 | offline |
| T32 | M05 | EOF／安静／timeout 不生成 false DONE | offline + live |
| T33 | M05 | 持久化失败时不输出成功结尾 | offline |
| T34 | M05 | 取消／异常后 callback、observer、订阅无泄漏 | offline |
| T35 | M06 | Journal 不可写时禁止新的远端 submit | offline |
| T36 | M06 | 文件与 DB 提交间崩溃不造成伪成功 | offline + recovery |
| T37 | M06 | 缺失证据出现在 manifest 盲区，不默认为已证实 | offline |
| T38 | M06 | 默认日志、fixtures、错误页无凭证和真实正文泄漏 | offline + manual audit |
| T39 | M06 | 删除正文后状态可解释、不能自动再生成 | offline |
| T40 | M06 | get_run／replay 不发模型请求或改变运行状态 | offline |
| T41 | M07 | loopback、key、Host/Origin 边界有效 | offline |
| T42 | M07 | 登录失效导致停止准入，不轮账号／发测试 prompt | offline + live |
| T43 | M07 | 专用 profile 及 browser generation 正确隔离 | offline + live |
| T44 | M07 | 第二进程拿不到排他锁，不能启动另一个 worker | offline + recovery |
| T45 | M07 | 队列、body、事件、时限预算不靠静默截断执行 | offline |
| T46 | M07 | artifact／恶意 URL 无法驱动 shell 或任意出站 | offline |
| T47 | M07 | 关闭／重启不把未知 run 清洗成 cancelled | offline + recovery |
| T48 | M08 | offline guard 阻断网络并拒绝真实个人凭证 | offline |
| T49 | M08 | RED 的原因对应目标行为，GREEN 穿过真实核心路径 | evidence audit |
| T50 | M08 | 相同 passed-count 不替代实际 bytes／行为差分 | evidence audit |
| T51 | M08 | live、mock、skip、unknown 的证据分开呈现 | evidence audit |
| T52 | M08 | 指定客户端的请求参数及截断流识别实际通过 | client + live |

## 3. 不变量覆盖索引

| 不变量 | 关键验收 |
|---|---|
| I01 事实纪律 | T03、T07、T08、T37 |
| I02 上下文隔离 | T05、T20、T21、T23 |
| I03 单 owner | T12、T18、T22、T44 |
| I04 不确定不重发 | T09、T14、T15、T19、T47 |
| I05 真实终态 | T16、T17、T32、T33、T36 |
| I06 流完整 | T27–T34、T52 |
| I07 精确清理 | T22、T24、T26、T34 |
| I08 无隐式降级 | T02、T03、T08、T25 |
| I09 凭证与数据保护 | T04、T38、T41、T42、T46、T48 |
| I10 共享运行核心 | T06、T09、T44 |
| I11 可解释证据 | T37、T39、T40、T51 |
| I12 验证不混淆 | T49–T52 |

## 4. 一个建议的高覆盖 exemplar

真实 core 接边界 fake transport，运行子进程，在写完 submitting intent 后、回执落库前退出进程；用同一 HOME 重启，断言 run=uncertain、上游 submit 计数仍为 1、generation admission 被阻止、get_run 可读、没有 false DONE。该 exemplar 需完整 RED→GREEN 与崩溃证据，不是只 mock 一个函数返回值。
