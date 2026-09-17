# Design

实现与边界见 `docs/architecture/direct-http-fixed-context-addendum.md`。

选择单个原子 bootstrap 文件而非多个独立旧 profile 文件，避免混合快照。新 direct 命令复用项目包命名空间，但不通过伪造 capability 开启旧 isolated API。一个额外小型 fixed-context journal 明確此模式的所有权与副作用，而不改写旧 Supervisor。

显式失败返回错误，未知结果阻塞重试。所有日志/API 错误使用安全分类，不原样打印 upstream body。
