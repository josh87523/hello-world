# content-engine-v1-archive Codebase Map

> 用于人和 AI 快速定位产品逻辑、运行逻辑和对应代码入口。先读 `docs/business-product-logic.md`，再按下表跳到具体模块。

## Module Entrypoints

| Area | Entry | Notes |
|---|---|---|
| 业务逻辑 | `docs/business-product-logic.md` | 历史归档边界 |
| 归档说明 | `README.md` | 目录说明、复用指引和 v2 对应关系 |
| 旧平台适配 | `platforms/` | 微信、小红书、即刻、Twitter 等旧发布适配 |
| 旧 pipeline | `core/, modules/, main.py` | v1 pipeline、scheduler 和内容模块 |
| 旧 prompt/配置 | `config/` | prompt 模板和配置参考 |
| 调研资料 | `docs/context/` | 60+ 小红书和内容运营调研 |

## Reading Contract

- 先用 `docs/business-product-logic.md` 判断这个仓库解决什么问题。
- 再按本页定位到代码或运行入口，避免从文件名猜产品逻辑。
- dated plan、archive、runtime data、generated output 只能当证据或历史参考，不能直接当当前运行合同。
- 涉及外部平台、账号、发布、支付、浏览器 profile 或凭证时，必须读真实运行面和权限边界，不能只读源码。

## Recommended First Read

1. `docs/business-product-logic.md`
2. `README.md`
3. `docs/context/`
4. `../content-engine/docs/business-product-logic.md`
