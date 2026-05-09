# 中期 → 最终：项目变更整理

**起点 commit**：`32a3159` （中期版本）
**统计**：51 次提交，59 个文件变更，约 +17,101 / -8,093 行

---

## 1. 仓库结构与工程化

把原本散落在根目录的脚本/笔记整理成标准 Python 项目布局，便于分工与测试。

- `3b0f2f2` 重组目录：新增 `apps/`、`scripts/`、`data/`、`docs/`、`notebooks/`
  - `case.md → data/case.md`，`case_audio_urls.json → data/case_audio_urls.json`
  - `api_test.js / generate_cases.js → scripts/`
  - 删除根目录 `Music AI.ipynb`（3,675 行）和 `web.html`（3,834 行）
- `38ea113` 给 `apps/`、`apps/api/` 加 `__init__.py`，作为正式 Python 包
- `pyproject.toml` (+35) 与 `requirements.txt` (+5) 新增/更新，固化依赖
- `.env.example` (+68)、README (+357/-) 全面对齐新结构与环境变量
- `.gitignore` 多次更新：忽略 `docs/`（后撤销）、`worktrees/`、对齐仓库结构
- `PRODUCT.md` (+43) 新增产品定位说明

---

## 2. 后端：API 与音乐 AI 引擎

### 2.1 API 服务（`apps/api/main.py`，+304）
- 新建 FastAPI 入口，承载 session、history、HealthKit mock 等接口
- `42b4b2b` `/api/healthkit/mock/run`：HealthKit 数据接入 mock 原型
- `2c00c1a` Soma MVP session flow + `docs/session-api-contract.md`（+115）

### 2.2 `music_ai_module` 重写
- `processor.py` 大改 (+816 / 涉及生理信号 → 情绪/唤醒度建模)
- `compiler.py` (+361) 重写音乐处方编译器
- `models.py` (+137)、`config.py` (+187)、`pipeline.py` (+155) 同步更新
- `style_maps.py` (+35) 新增风格映射
- `personalization.py` (+187) **新增个性化模块**
  - `9ea9287` 个性化音乐策略 + 加固生理信号管线
- `45e89d7` 连续唤醒度模型（continuous arousal）+ `MusicStrategy`

### 2.3 知识库（GraphRAG）—— **本阶段最大新增模块**
全新 `music_ai_module/knowledge/` 子包：
| 文件 | 行数 | 作用 |
|---|---|---|
| `schemas.py` | 240 | 实体/关系/证据 Pydantic 模型 |
| `retriever.py` | 238 | 混合 dense + lexical 检索 |
| `graph_store.py` | 166 | 图存储与合并 |
| `auditor.py` | 152 | 临床证据审计 |
| `extractor.py` | 111 | 文档抽取 |
| `fetcher.py` | 110 | 来源抓取 |
| `embeddings.py` | 100 | 向量嵌入 |
| `cli.py` | 204 | 命令行接口 |
| `sources.py` / `paths.py` / `__main__.py` | 86 | 工具与入口 |

种子数据：`data/knowledge/` 下新增 `chunks.jsonl`、`graph.json` (+577)、`sources.yaml` (+76)、README (+60)

相关提交：
- `8079706` 本地 GraphRAG 临床音乐知识管线
- `4e9f32e` 扩展知识种子数据 + 完整性测试
- `cc61cfa` 多语言词法 token + 混合 dense-lexical 检索

---

## 3. 前端：Web 应用 (`apps/web/index.html`, +9,866 行)

整个 Web 端从单文件 `web.html` 重构为完整的 SPA 应用。

### 3.1 整体架构
- `9e1f0df` **侧边栏 App Shell**，多 workspace 视图（核心架构变更）
- `3a845c0` `sidebar-reconstruct` 分支合入
- `e588bce` 接入 Tailwind 字号体系，统一排版

### 3.2 Session 流程
- `2c00c1a` MVP session flow（含 history、feedback）
- `e8433ff` Session 拆分为 **check-in / playback** 两屏
- `202452a` 统一 MindWave 管线作为体征与 prompt 单一数据源
- `fe5f92d` 移除冗余的 session 参数控制面板
- `7c3ee04` `5eb3a2d` `ddacc65` `f178dec` 多轮布局/滚动/触控修复

### 3.3 Settings 改造
- `3dbe611` Settings 改为侧边栏 + tab panels
- `5b8f744` 扩充 Preferences / Privacy / Integrations
- `94952fc` 排版、动效曲线、a11y 细节打磨

### 3.4 Diagnostic Report
- `ed3f7bb` Jump nav 移到 scroll 容器外，避免遮挡
- `d7306bd` Jump nav 折行 + scrollspy + scroll margin
- `3e... → 4c9067c` Full Report 默认、布局拆分、纯 LLM、移除 Monthly

### 3.5 History & Demo
- `72266a0` 通过 `somaSeedDemoHistory()` 用 5 个 `DEMO_CASES` 种子化 history
- `a6aa61b` 页面加载时自动合并 demo session
- `b016b44` 重新生成 5 个 demo case 的 Suno 缓存音轨
- `e6aea83` Demo report 英文化 + 同步 demo history seed
- `1cbe833` History 布局、列表行、calm/help 元信息行优化

### 3.6 品牌与视觉
- `af248e7` 更新 Soma 品牌图标
- `17d8110` `02eba0c` `f512e27` Soma wordmark 字体 / 字号 / 字距迭代
- `afff047` EQ 进度与动画平滑、Report 流程收紧

---

## 4. 测试 (`tests/`)

从无到有补齐 **12 个测试文件**：

| 测试 | 行数 |
|---|---|
| `test_processor.py` | 134 |
| `test_compiler.py` | 107 |
| `test_knowledge_retriever.py` | 101 |
| `test_healthkit_mock_api.py` | 88 |
| `test_clinical_auditor.py` | 75 |
| `test_pipeline.py` | 58 |
| `test_knowledge_schemas.py` | 54 |
| `test_knowledge_seed_data.py` | 50 |
| `test_personalization.py` | 43 |
| `test_knowledge_graph_merge.py` | 41 |
| `test_knowledge_extractor.py` | 16 |
| `conftest.py` + `__init__.py` | 32 |

合计 ~800 行测试代码，覆盖 processor / compiler / pipeline / personalization / knowledge / healthkit。

---

## 5. 文档

- `docs/mvp-prd.md` MVP 产品需求
- `docs/stage-1-mvp-session-flow.md` (+58) Session 流程
- `docs/session-api-contract.md` (+115) API 契约
- `docs/demo-script.md` (+47) Demo 演示脚本
- `docs/superpowers/plans/2026-05-01-ios-migration-foundation.md` (+1,782) **iOS 迁移基础规划**（重大长期规划文档）
- `notebooks/pipeline_demo.ipynb` (+80) 可执行 demo notebook

---

## 6. 配置与环境

- `a44b57f` `LLM_BASE_URL` 默认值改为 OpenAI `api.openai.com/v1`
- `47b0ae5` 扩展 `.env.example`，README 与之对齐
- `075e5a9` README markdown 表格对齐
- `773b777` README 更新 MindWave 品牌与系统配置

---

## 7. 关键里程碑（按时间）

1. **结构重组**（`3b0f2f2` 起）：项目工程化基础
2. **音乐 AI 引擎升级**：连续唤醒度模型、个性化、生理信号管线加固
3. **知识库 GraphRAG**：从零搭建临床音乐知识图谱 + 混合检索
4. **Web SPA 重构**：单文件 → Sidebar 多 workspace 应用，session/settings/report/history 全面重做
5. **HealthKit + iOS 规划**：mock API + 1,782 行迁移规划文档
6. **Demo 数据与体验打磨**：5 个 demo case、英文化、动效收尾
7. **测试覆盖**：补齐核心模块单测
