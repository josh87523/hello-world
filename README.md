# Content Engine v1 Archive

> **状态：已归档。** 继任项目 → `~/Workspace/content-engine`
>
> 本仓库是 content-engine 的第一版原型，包含多平台自媒体发布系统和早期调研数据。
> 不再活跃维护，仅作历史参考。已被 `.claudeignore` 排除。

## 目录说明

| 目录 | 类型 | 说明 | content-engine v2 对应 |
|------|------|------|----------------------|
| `platforms/` | 旧代码 | 多平台发布适配（微信、小红书、即刻、Twitter、Instagram、Threads） | `content_engine/` 已重写 |
| `core/` | 旧代码 | pipeline、scheduler、multi_publish | `content_engine/` 已重写 |
| `modules/` | 旧代码 | 内容生成、改写、优化模块 | `content_engine/` 已重写 |
| `models/` | 旧代码 | 数据模型 | `content_engine/` 已重写 |
| `ai/` | 旧代码 | AI 调用封装 | `content_engine/` 已重写 |
| `config/` | 旧代码 | 配置 + prompt 模板 | 部分 prompt 可参考 |
| `integrations/` | 旧代码 | 外部服务集成 | — |
| `docs/context/` | 调研资料 | 60+ 小红书调研（运营、选题、封面、AI 内容等） | 按需引用到 v2 docs/research/ |
| `main.py` | 旧代码 | 主入口（42KB 单文件） | v2 已拆分 |
| `profiles/` | 敏感数据 | 浏览器 profile（已 gitignore） | HanxuKeji 管理 |
| `data/` | 数据 | 测试数据 | — |

## 复用指引

如果 content-engine v2 需要参考本仓库：

1. **平台能力清单**：`platforms/` 下各文件的接口定义，了解 v1 支持哪些平台操作
2. **Prompt 模板**：`config/prompts/` 下的 viral_formulas、optimization、content_recreation
3. **小红书调研**：`docs/context/xiaohongshu_research/` 按主题分类的 60+ 篇调研
4. **运营方案**：`docs/context/AI同人文写作小红书运营方案.md`

不建议直接复用 `core/`、`modules/`、`main.py` 的代码——v2 架构已完全重写。
