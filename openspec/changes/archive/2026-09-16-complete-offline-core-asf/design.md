# Design: offline readiness, not a fabricated live adapter

## Decisions

1. 保留原14个生产模块，在原调用路径扩展；只新增 safe errors、共享 HomeLock、UnconfiguredTransport 与 CLI，不新建平行核心。
2. Journal 成为同一运行目录唯一拥有者。短事务使用 RLock＋嵌套 SAVEPOINT；WAL/FULL。失败 COMMIT 回滚，活动 worker 退出前不释放 OS 锁。
3. 入队事务冻结用户意图、账号、上下文版本、能力与预算，并生成完整 fingerprint。执行时旧 optional 参数只核对，不能替换。并发相同幂等键只产生一个 run。
4. 写资源操作意图→准备精确 context→写 submit intent→单次 submit→独立提交 receipt→核对 context→观察与归一→持久化结果＋索引＋终态。receipt 即使与 context 冲突也保留，但不会用于不加校验的恢复。
5. 终态不是首个／最后事件获胜；全部已观察事件必须无身份、顺序、文本或终态冲突。空结果与缺失结果分开。没有结局或失败不明确时 uncertain。
6. 只读 reconcile 仅查原 handle，核对原账号和工作区。无 receipt 或有矛盾需本机人工取证；不新增猜测式人工清闸 API。
7. 单 generation mutex＋一个队列 worker。HTTP 通过 lifespan、SDK 通过 context manager 关闭；stuck I/O 不强行释放锁。网络 I/O 硬截止由 transport 履行，核心作边界监督。
8. 默认未配置，无假 verified 能力；mock 显式选择并在结果／健康／模型表标识。live 不在本环境实现。
9. 原生 API 与 daemon SDK 完成闭环，Chat Completions 只支持单 user 文本非流式。HTTP 不回显校验失败的原始输入或本地结果路径。

## Alternatives rejected

不通过增加后台、分布式任务框架、账号池或完整模型路由来解决当前缺口；不通过屏蔽异常、删除审计测试、降低不变量解决假成功。线程仅用于一条阻塞 transport worker，不声称能强杀任意阻塞网络函数。

## Validation approach

原43项审计先在未改基线运行得到22失败/21通过，再修复；原19保留。新增41项测试覆盖副作用、并发、进程崩溃、持久化和真实loopback。最后7个边界明确记录了 RED→GREEN；另外34个新增用例是新增完成后执行，不虚构逐项RED。详见 verification。

ponytail: reuse existing modules → stdlib sqlite/threading/fcntl/fsync → installed FastAPI/Pydantic/httpx/Uvicorn；没有新增运行依赖族或宏观平台。
