# M06 Journal、结果存储与证据链

> v0.1.0 · draft。学习 ValueHermes 的账别纪律与可追溯报告，不复制三库或遥测平台。首版一库，关键合同按表／字段分工。[V1](../../research/prior-art-prb/sources.md#v1)

## 1. 定位与本地目录

建议运行目录 `PRISM2API_HOME`，未配置时拟用 `~/.prism2api`；这是设计值，不是本次已创建的安装目录。

```text
PRISM2API_HOME/
  runtime.db              # 状态、提交账、上下文、证据索引
  inputs/                 # 受保护的原始输入；独立保留与清除策略
  results/                # 有保留策略的正文与 artifact 描述
  evidence/               # 脱敏机器可读 manifest
  credentials/            # 仅本机授权材料；不进入日志
  browser-profile/        # 仅需要浏览器时，专用且不与日用 profile 共用
  logs/                   # 缺省仅结构化元数据
  locks/                  # 单实例 OS 锁；文件存在本身不等于已加锁
```

离线 fixtures 位于未来 repo 的 `tests/fixtures/`，不引用个人运行目录。

## 2. 最小逻辑表

| 表／集合 | 所有者 | 重要约束 |
|---|---|---|
| `runs` | M03 | run_id 唯一；state_version CAS；结果仅在成功事务关联 |
| `submit_attempts` | M03 | 首版每 run 最多一次生成 attempt；记录 intent 与回执 |
| `resource_operations` | M03/M04 | 远端创建／取消等写操作意图先落账 |
| `idempotency_records` | M03 | principal＋key 摘要唯一；与 run 原子绑定 |
| `contexts` | M04 | owner 与 context_revision；不能按客户端随意 ID 越权 |
| `capability_evidence` | M02 | evidence 与 activation 两轴，版本与 account 范围明确 |
| `event_metadata` | M05/M06 | 运行序号、类型、来源引用；默认不存原始正文或 Cookie |
| `deliveries` | M05（语义）/M06（存储） | 每次消费独立 delivery_id；不覆盖 run 终态或别的交付 |
| `result_index` / `manifest_index` | M06 | 引用、散列、版本、保留期限、可用状态 |

以上是逻辑清单，不要求每项独立 ORM 模型。物理 schema 在首个存储 change 中实现迁移与测试；目前没有建库，也没有已发布迁移。

## 3. SQLite 使用边界

采用一个受控写入通道和短事务；不得在数据库事务内做 Playwright / HTTP await。read-only 查询不改变 run、触发刷新或发 prompt。

WAL、同步级别、busy timeout 与连接线程策略必须作为实现决策记录并有崩溃测试；不因为选择 SQLite 就宣称掉电永不丢账。异步服务中可用专用线程串行数据库 I/O，先复用标准库，不为少量写入引入 ORM、Redis 或完整 event-sourcing 框架。

数据库异常先关闭新准入。Journal 不可写时，禁止继续向上游提交任务。磁盘满不能降级到“无日志继续跑”。

## 4. 结果提交的两阶段文件／数据库边界

SQLite 与文件系统不是一个原子事务。建议流程：在同一文件系统写临时结果与 manifest，校验并 flush 到约定持久化级别，原子改名，再在数据库短事务中关联这些文件并把 run 置 succeeded。具体 fsync 及目录持久化由实现测试明确。

崩溃在文件改名后、DB 提交前：允许出现无索引孤儿文件，由只读核验工具发现，不能把“有个结果文件”直接当 run 成功。DB 中 succeeded 但文件丢失／摘要不符：返回完整性错误或结果不可用，不返回空字符串冒充答案，也不自动再生成。

流式 `[DONE]` 只能在成功事务之后发出。已送出的部分文本不具备耐久完整结果的地位。

## 5. `EvidenceManifest`：不复制整段秘密流量

| 字段 | 说明 |
|---|---|
| `manifest_schema_version`、`run_id` | 可解析的版本与稳定关联 |
| `request_fingerprint` | 带本地秘密的摘要；说明规范化版本 |
| `requested_alias`、`model_evidence` | 请求标签与确认事实分开 |
| `capability_snapshot_ref` | 本次启用能力及依据 |
| `context_binding_ref`、`context_limitations` | 使用的上下文、隔离范围和盲区 |
| `submit_attempt_ref`、`remote_handle_ref` | 本地提交意图与远端回执关联 |
| `completion_evidence` | 完成依据、parser 版本、完整性状态 |
| `output_digest`、`result_ref` | 完整结果指纹和受保护引用 |
| `delivery_summary` | manifest 提交时已知的交付快照；未发生的最终交付为 unknown，不预写 completed |
| `timings` | 可观测阶段时长，无法观测为 null |
| `limitations`、`redaction_version` | 未证明事项与脱敏版本 |
| `replay_fixture_ref` | 可空；仅脱敏测试样本可用于离线回放 |

成功结果的 manifest 在最终 HTTP sentinel 之前提交，因此不可能先证明该 sentinel 已送达。后续交付结果只更新独立 deliveries 记录，查询时组合呈现，不回写已经散列绑定的 manifest；交付完成也不反证调用方应用已收到。

**每个 run 有 manifest 不等于每个 run 的所有事实都已证明。** 未捕获的回执、未知模型、无法完整观察的上下文必须显式标记。replay 是解析与行为证据回放，不默认重新调用 LLM，不能把重生成当作复现原答案。

## 6. 数据保留、删除与隐私

结果正文为恢复所需，可在经确认的本地保留策略下持久化；默认日志只记录元信息，不记录 prompt、回答正文、Cookie、Authorization、账号邮箱或远端含 token 的 URL。凭证文件与普通 evidence 完全分开。

输入正文、结果正文、事件元数据、凭证缓存、幂等 tombstone 分别配置保留期和容量；实现不得给所有材料一个无限 TTL。期限当前未标定，首次启动前须给出明确策略并校验非空，不把未知期限硬编进架构。

删除结果正文后，run 仍可返回状态与“已清除”，但不能补生成。保留最少 key tombstone 的窗口及用途要透明；如果用户选择完全删除相关去重记录，明确说明未来重试可能被当作新意图。

本地散列不是匿名化。短 prompt 的普通 hash 容易泄露，所以 fingerprint 采用本地 key；key 丢失或轮换需要兼容迁移计划，不能默默丢弃旧键并重投所有请求。

## 7. 日志、指标与可观察性

首版采用结构化事件和原生 run 查询，不引入强制 SaaS、遥测 agent 或 metrics 服务。

建议测量：queue wait、submit-ack、time-to-first-visible-output、total run time、完整成功率、uncertain 比率、取消确认率、清理失败、能力漂移。指标维度不含正文和用户标识，样本数量与观测窗口随报告一起给出。

文本输出质量与网关可靠性分开；网关不能用一个模型评审分数证明没有丢流、没有串上下文。技术数值由实际计时、计数与证据计算，不靠模型填。

## 8. 验收与未决

`T35` Journal 写失败阻止 submit；`T36` 文件／DB 崩溃窗不伪成功；`T37` manifest 缺证据显式 unknown；`T38` 日志与 fixture 脱敏检查；`T39` 删除策略保留状态且不补生成；`T40` 查询与 replay 无网络副作用。

未决 `U11` 用量、`U14` 数据保留与预算，见 [A2](../appendices/a2-evidence-and-open-questions.md)。物理 schema、同步参数和迁移命令属于实现 change，不能在本文假装已验证。
