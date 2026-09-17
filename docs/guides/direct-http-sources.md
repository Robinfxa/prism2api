# Direct HTTP provenance

本实现基于用户授权完成 prism2api 的请求，以及此前仓库中积累的合同。没有将用户上传的浏览器解密材料或旧会话凭据用于开发、测试或打包。

## 固定参考

- Robinfxa/prism2api: `59bbe747b35e931f082ffbfa1e19be2294450280`。GitHub connector 核对。远端无 `e9ac985` 的可读提交时，不假定未推送本地变更已消失；合入工具保留已有工作，dirty tree 拒绝写入。
- Danchuna/prismctl2api: `95fab6f3a30915f7cbb66864fb70e0cf31629b3f`。
  - https://github.com/Danchuna/prismctl2api/blob/95fab6f3a30915f7cbb66864fb70e0cf31629b3f/main.go
  - https://github.com/Danchuna/prismctl2api/blob/95fab6f3a30915f7cbb66864fb70e0cf31629b3f/gateway.go
  - https://github.com/Danchuna/prismctl2api/blob/95fab6f3a30915f7cbb66864fb70e0cf31629b3f/grab_token.py
  - https://github.com/Danchuna/prismctl2api/blob/95fab6f3a30915f7cbb66864fb70e0cf31629b3f/LICENSE
- Python shlex: https://docs.python.org/3/library/shlex.html
- HTTPX timeouts: https://www.python-httpx.org/advanced/timeouts/

## 已采用的同行线索

`metadata.codex_listen_snapshot`、`x-crixet-sandbox-token` heartbeat、同源 bootstrap、更新后的 turn_state。同行代码是第三方协议证据；没有在本环境升级成“Prism 当前已独立实测”。特别没有承诺缺少某字段一定解释原 sandbox 401，也没有从一次 401 推导出浏览器是否必要。

## 独立实现而非整仓移植

新的 Python 模块自行编写，不复制同行的 Go gateway、UI、工具桥接。致谢保留在本文件；未采用自动 start 重试、估算 usage、已执行沙箱工具再投影为客户端执行请求等行为。

## 许可

本包新增 direct 模块、其测试与文档采用 `LICENSE.direct` 的 MIT 许可。旧仓库/工作流资料的原有许可状态没有被此补丁擅自更改；需要为整个仓库确定许可证时，应同时检查已有第三方代码。对 Prism 服务的调用仍须符合适用的账户权限和条款；开源代码许可不是上游服务的使用授权。
