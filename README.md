# 智汇 · AskKB — 企业级双通道 RAG 知识库平台

> 一个让企业「敢用」的检索增强生成（RAG）知识问答平台：**回答必有引用、低置信必拒答、检索必过权限过滤、全程可审计、质量可度量**。
> 基于 **LangChain + FastAPI + React**，模型层对接 **阿里云百炼（DashScope）**，一套知识库底座同时服务「**对客智能客服**」与「**对内员工知识**」两类场景。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](backend/requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-red)](https://python.langchain.com/)
[![React](https://img.shields.io/badge/React-18-61dafb)](frontend/package.json)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📌 项目简介

企业多年积累的产品手册、售后 FAQ、内部制度等知识散落在网盘 / 邮件 / Wiki 中，AI「读不懂也找不到」；直接套用通用大模型又会产生幻觉、无溯源、权限失控。AskKB 面向这些问题，提供一套**可运营、带权限隔离、质量可度量**的企业级 RAG 系统：离线批量导入文档构建向量索引，在线提供带引用与拒答兜底的智能问答。

- 需求定义见 [`AskKB-企业级RAG知识库-PRD.md`](AskKB-企业级RAG知识库-PRD.md)
- 架构设计见 [`AskKB-企业级RAG知识库-技术方案.md`](AskKB-企业级RAG知识库-技术方案.md)
- 工程实现参考并生产化了教学示例 [RagLangChainTest](https://github.com/NanGePlus/RagLangchainTest)（LCEL 检索链、Reranker、对话记忆、PDF 表格预处理）

---

## ✨ 核心特性

| 特性 | 说明 |
|---|---|
| 🛰️ **双通道架构** | `employee_kb`（员工手册，重权限/密级）与 `cs_agent`（智能客服，重体验/强制审核+转人工）一套底座差异化服务 |
| 🔐 **双层权限过滤** | 第一层按有权知识库限定 collection；第二层查询强制注入密级/部门 metadata 过滤，未授权知识物理+逻辑双层不可召回 |
| 📚 **知识库与文档管理** | 知识库 CRUD、多格式文档上传（PDF/Word/PPT/Excel/MD/HTML/TXT）、版本管理、密级/生效期元数据、切分预览 |
| ⚙️ **离线入库流水线** | 解析 → 切分（中/英双策略）→ 批量 Embedding → 带溯源 metadata 写向量库 → 入库自检；Celery 异步任务与进度追踪 |
| 🔍 **混合检索 + Rerank** | 多 collection 并行召回 topN → 关键词/向量混合 → Reranker 精排取 topK，精排分数用于置信判定 |
| ✅ **引用溯源 + 低置信拒答** | 每条实质性回答附来源文档/页码/片段/[n] 标注；置信度低于阈值走拒答（对内）/转人工（对客），无引用即拒答，杜绝幻觉 |
| 💬 **多轮对话记忆** | 会话级记忆（Redis，最近 N 轮拼接），支持指代追问 |
| 📡 **OpenAI 兼容 + SSE 流式** | 提供 `/v1/chat/completions` 兼容端点与 `/api/ask`，支持流式与非流式输出 |
| 📊 **运营看板 + 反馈闭环** | 自助解决率/拒答率/平均置信度统计；问答点赞点踩反馈回流 |
| 🧾 **可观测与审计** | trace_id 贯穿全链路中间件、JWT 鉴权、限流配置、Prometheus 指标 |
| 🎛️ **管理端 Web UI** | React + Ant Design 后台：登录、看板、知识库、文档、问答 |

---

## 🔄 双通道设计（本项目的核心）

AskKB 将「两类 RAG 场景」收敛为一级配置维度 `ChannelConfig`（[backend/app/services/channel_service.py](backend/app/services/channel_service.py)），业务链路对通道无硬编码分支，新增通道只需加配置：

| 配置项 | `employee_kb` 企业员工手册 | `cs_agent` 智能客服问答 |
|---|---|---|
| 面向对象 | 内部员工 | C 端客户 |
| 可召回密级 | 公开 / 内部 / 机密（按用户密级上限） | **强制仅「公开」**（对客永不召回内部/机密） |
| Rerank topK | 5（更全） | 3（更快） |
| 拒答阈值 | 0.35 | **0.45**（宁可不答） |
| Temperature | 0.3（可总结） | 0.0（求稳） |
| 最大并发 | 50 | 200 + 全局熔断 |
| 内容审核 | 关闭 | **强制开启** |
| 拒答后动作 | 拒答话术 / 联系管理员 | **转人工兜底** |
| Prompt 人格 | 企业内部知识助手 | 友好简洁客服，禁泄内部信息 |

---

## 🏗️ 系统架构

```
┌──────────────────────────── 前端 (React + Ant Design) ───────────────────────────┐
│   登录 · 运营看板 · 知识库管理 · 文档管理 · 智能问答(QAChat, SSE 流式)              │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                                     │ HTTP / SSE (Vite proxy)
┌──────────────────────────────── 后端 (FastAPI) ──────────────────────────────────┐
│ 中间件: TraceMiddleware(trace_id) · CORS · JWT 鉴权 · RBAC 权限点                   │
│ ── API 层 ──  /api/auth  /api/kb  /api/documents  /api/ask  /v1/chat/completions    │
│ ── 编排层 ──  RAGService: 通道解析→记忆→双层权限过滤→混合检索→Rerank→置信判定→       │
│                            LLM 生成→引用校验→落审计 (对应技术方案 §6.2)              │
│ ── 服务层 ──  ChannelService · VectorStore(Chroma/Qdrant) · Embedding · Rerank ·     │
│               LLM(DashScope) · Memory · Document · KB                               │
└──────┬──────────────────┬───────────────────┬──────────────────┬─────────────────┘
       │                  │                   │                  │
┌──────▼──────┐   ┌───────▼────────┐   ┌──────▼───────┐   ┌──────▼──────────────┐
│ 向量库       │   │ 关系库 MySQL/   │   │ Redis         │   │ 阿里云百炼 DashScope │
│ Chroma(dev) │   │ SQLite(dev)    │   │ 会话·限流·队列 │   │ qwen-plus /          │
│ Qdrant(prod)│   │ 元数据·权限·审计 │   │ (可选)        │   │ text-embedding-v4 /  │
└─────────────┘   └────────────────┘   └──────────────┘   │ gte-rerank           │
                                                            └─────────────────────┘
```

---

## 🧱 技术栈与依赖

### 运行时环境要求（先备齐这些工具）

| 工具 | 版本要求 | 用途 | 必需 |
|---|---|---|---|
| **Anaconda / Miniconda** | 任一版本 | Python 虚拟环境管理（**本项目环境名 `langchain-rag`**） | ✅ **推荐** |
| **Python** | 3.10+（建议 3.11，由 conda 环境提供） | 后端运行环境 | ✅ |
| **Node.js** | 18+（建议 20 LTS） | 前端构建（Vite） | ✅ |
| **npm / pnpm** | 随 Node | 前端包管理 | ✅ |
| **阿里云百炼 API Key** | `DASHSCOPE_API_KEY` | 调用 qwen-plus / embedding / rerank | ✅ **核心** |
| **Docker + Docker Compose** | v24+ | 一键启动后端与 Redis | 推荐 |
| **Redis** | 7.x | 会话记忆 / 限流 / Celery 队列 | 可选（无则降级为内存） |
| **Git** | 2+ | 代码克隆 | ✅ |

> ⚠️ 本项目模型能力（生成 / 向量化 / 精排）**完全依赖阿里云百炼 DashScope**，运行前必须设置环境变量 `DASHSCOPE_API_KEY`（兼容 `DASH_SCOPE_API_KEY`）。前往[百炼控制台](https://bailian.console.aliyun.com/)开通并获取 API Key。

### 后端主要依赖（[backend/requirements.txt](backend/requirements.txt)）

| 类别 | 依赖包 | 版本 |
|---|---|---|
| Web 框架 | `fastapi` / `uvicorn[standard]` / `python-multipart` | 0.115.6 / 0.34.0 / 0.0.18 |
| ORM & 数据库 | `sqlalchemy` / `aiosqlite` / `alembic` / `pymysql` | 2.0.36 / 0.20.0 / 1.14.0 / 1.1.1 |
| 缓存/队列 | `redis` / `celery[redis]` | 5.2.1 / 5.4.0 |
| 认证安全 | `python-jose[cryptography]` / `bcrypt` / `python-dotenv` | 3.3.0 / ≥4.1 / 1.0.1 |
| 校验/配置 | `pydantic` / `pydantic-settings` | 2.10.3 / 2.6.1 |
| RAG 框架 | `langchain` / `langchain-core` / `langchain-text-splitters` / `langchain-community` | 0.3.x |
| 向量库 | `chromadb` / `langchain-chroma` | 0.5.18 / 0.2.1 |
| 大模型 | `dashscope`（百炼 SDK） | 1.20.11 |
| 文档解析 | `pypdf` / `python-docx` / `openpyxl` / `python-pptx` / `beautifulsoup4` | 见文件 |
| HTTP 客户端 | `httpx` / `aiohttp` | 0.28.1 / 3.11.10 |
| 流式/重试/监控 | `sse-starlette` / `tenacity` / `prometheus-fastapi-instrumentator` | 2.1.3 / 9.0.0 / 7.0.2 |

### 前端主要依赖（[frontend/package.json](frontend/package.json)）

| 类别 | 依赖包 | 版本 |
|---|---|---|
| 框架 | `react` / `react-dom` | ^18.3 |
| 语言/构建 | `typescript` / `vite` / `@vitejs/plugin-react` | ~5.6 / ^6.0 / ^4.3 |
| UI 组件库 | `antd` / `@ant-design/icons` | ^5.22 / ^5.5 |
| 路由 | `react-router-dom` | ^6.28 |
| 状态管理 | `zustand` | ^5.0 |
| HTTP | `axios` | ^1.7 |
| Markdown 渲染 | `react-markdown` | ^9.0 |
| 时间处理 | `dayjs` | ^1.11 |

---

## 🚀 快速开始

### 方式一：一键 Docker（后端 + Redis）

```bash
# 1. 克隆项目
git clone https://github.com/<your-name>/LangchainRag.git
cd LangchainRag

# 2. 配置百炼 API Key（二选一）
export DASHSCOPE_API_KEY=sk-xxxxxxxx          # Linux/macOS
set DASHSCOPE_API_KEY=sk-xxxxxxxx             # Windows PowerShell/CMD

# 3. 启动后端与 Redis（前端另用 npm 跑）
docker-compose up -d
#   后端 API:     http://localhost:8000
#   交互式文档:   http://localhost:8000/docs

# 4. 启动前端（新终端）
cd frontend
npm install
npm run dev
#   前端页面:     http://localhost:5173
```

### 方式二：本地开发（Windows 一键脚本 · Anaconda）

仓库根目录提供 [`start-dev.bat`](start-dev.bat)：自动校验 API Key → **定位 conda 环境 `langchain-rag` 的 python 解释器**（支持脚本顶部 `CONDA_PYTHON` 手动指定）→ 用该环境 `python -m pip` 装后端依赖 → 以 **`python -m app.main`** 拉起后端（:8000）与前端（:5173）。

```bash
# 1. 先确保已 export/set DASHSCOPE_API_KEY，然后双击或执行：
start-dev.bat

# 2. 若自动探测不到 conda 环境，可在脚本顶部手动指定：
#    set "CONDA_PYTHON=C:\Users\<你>\.conda\envs\langchain-rag\python.exe"
#    （或修改脚本顶部 CONDA_ENV 切换环境名）
```

### 方式三：Anaconda 环境手动启动（本项目当前使用）

> 本项目使用 **Anaconda** 管理 Python 虚拟环境，环境名为 **`langchain-rag`**；启动后端统一使用 `python -m` 方式，直接调用该 conda 环境内的 python 解释器，确保解释器与依赖一致。

**1）首次创建环境并安装依赖**

```bash
conda create -n langchain-rag python=3.11 -y     # 已创建可跳过
conda activate langchain-rag
cd backend
pip install -r requirements.txt
```

**2）启动后端（在 `langchain-rag` 环境内，使用 `python -m` 指定模块入口）**

```bash
conda activate langchain-rag          # 若尚未激活
cd backend
python -m app.main                     # 执行 app/main.py 的 __main__ 入口，按 config 端口(:8000)启动
```

未激活环境时，可显式调用该 conda 环境内的 python 解释器：

```bash
# Windows
%USERPROFILE%\.conda\envs\langchain-rag\python.exe -m app.main
# Linux / macOS
~/miniconda3/envs/langchain-rag/bin/python -m app.main
```

> 如需热重载调试，也可用：`conda run -n langchain-rag uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

**3）启动前端**

```bash
cd frontend
npm install
npm run dev                            # Vite 已将 /api、/v1 代理到 http://127.0.0.1:8000
```

> 若不使用 Anaconda，也可改用标准 venv：`python -m venv .venv && source .venv/bin/activate`（Windows 为 `.venv\Scripts\activate`），后续步骤相同。

### 访问入口

| 地址 | 说明 |
|---|---|
| http://localhost:5173 | 管理端 Web UI（登录 / 看板 / 知识库 / 文档 / 问答） |
| http://localhost:8000/docs | Swagger 交互式 API 文档 |
| http://localhost:8000/health | 健康检查 |
| http://localhost:8000/metrics | Prometheus 指标 |

---

## ⚙️ 配置项说明

所有配置经环境变量注入（[backend/app/config.py](backend/app/config.py)，支持 `backend/.env`），关键项如下：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | —（必填） | 百炼 API Key，核心依赖 |
| `LLM_MODEL` | `qwen-plus` | 生成模型 |
| `EMBEDDING_MODEL` | `text-embedding-v4` | 向量化模型 |
| `RERANK_MODEL` | `gte-rerank` | 精排模型 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/askkb.db` | 元数据库（生产换 MySQL） |
| `VECTOR_STORE_TYPE` | `chroma` | 向量库类型（`chroma` / `qdrant`） |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant 地址（prod） |
| `REDIS_URL` | `redis://localhost:6379/0` | 会话/队列（无则降级内存） |
| `SECRET_KEY` | dev 占位值 | **生产必须替换**，用于 JWT 签名 |
| `RETRIEVAL_TOP_N` / `RERANK_TOP_K` | 20 / 5 | 粗排召回数 / 精排保留数 |
| `DEFAULT_REJECT_THRESHOLD` / `CS_REJECT_THRESHOLD` | 0.35 / 0.45 | 对内 / 对客拒答阈值 |
| `MAX_UPLOAD_SIZE_MB` / `MAX_UPLOAD_PAGES` / `MAX_BATCH_UPLOAD_COUNT` | 50 / 500 / 100 | 上传限制 |
| `RATE_LIMIT_PER_MIN` | 20 | 每用户每分钟问答限流 |
| `CORS_ORIGINS` | `http://localhost:5173,...` | 允许的前端来源 |

> **接入本地 MySQL / Redis（本项目当前环境）**
> 元数据库默认用 SQLite 免安装；若要连本地 MySQL（示例 `127.0.0.1:13306`，`root:root`），在 `backend/.env` 设置异步连接串并先建库：
>
> ```bash
> # 1) 先建库（create_all 只建表不建库）
> #    CREATE DATABASE askkb DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
> # 2) .env 指定连接串（异步驱动 aiomysql，已在 requirements.txt）
> DATABASE_URL=mysql+aiomysql://root:root@127.0.0.1:13306/askkb?charset=utf8mb4
> REDIS_URL=redis://127.0.0.1:6379/0
> ```
>
> 注意：SQLAlchemy 异步引擎必须用 `mysql+aiomysql://`（不能用同步的 `pymysql`）；Redis 端口 6379 供会话记忆(db0)与 Celery(db1/db2) 共用，未启动时后端自动降级为内存。

---

## 📡 API 概览

| 方法 | 路径 | 说明 | 鉴权 |
|---|---|---|---|
| POST | `/api/auth/register` · `/login` · `/refresh` · `/me` | 注册/登录/刷新/当前用户 | 部分 |
| POST | `/api/kb` | 创建知识库 | ✅ |
| GET/PUT/DELETE | `/api/kb/{kb_id}` | 知识库详情/编辑/删除 | ✅ |
| POST/GET/DELETE | `/api/kb/{kb_id}/permissions` | 知识库授权管理 | ✅ |
| POST | `/api/documents/upload` | 上传文档并触发入库 | ✅ |
| GET/PUT/DELETE | `/api/documents/{doc_id}` | 文档详情/元数据/删除 | ✅ |
| GET | `/api/documents/{doc_id}/versions` · `/tasks` | 版本 / 入库任务 | ✅ |
| POST | `/api/documents/{doc_id}/preview-split` | 切分预览 | ✅ |
| POST | `/api/ask` | 核心问答（流式/非流式，带 channel） | ✅ |
| POST | `/v1/chat/completions` | OpenAI 兼容问答 | ✅ |
| GET | `/api/conversations` · `/api/conversations/{id}/messages` | 会话与历史 | ✅ |
| POST | `/api/feedback` | 问答点赞/点踩反馈 | ✅ |
| GET | `/api/dashboard/knowledge-ops` | 运营看板统计 | ✅ |

**问答示例（非流式）：**

```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"channel":"cs_agent","question":"这款机型支持7天无理由退货吗？","stream":false}'
```

返回含 `answer`、`citations[]`（文档/页码/片段/分数）、`confidence`、`refused`、`handoff`、`trace_id`。

---

## 📁 项目结构

```
LangchainRag/
├── AskKB-企业级RAG知识库-PRD.md          # 产品需求文档
├── AskKB-企业级RAG知识库-技术方案.md      # 技术方案文档
├── docker-compose.yml                     # 后端 + Redis 一键启动
├── start-dev.bat                          # Windows 本地开发快速启动
├── backend/
│   ├── requirements.txt                   # Python 依赖
│   ├── Dockerfile
│   ├── .env                               # 环境变量配置
│   └── app/
│       ├── main.py                        # FastAPI 入口 + 生命周期
│       ├── config.py                      # 全局配置（环境变量）
│       ├── api/                           # 路由: auth / kb / document / qa
│       ├── core/                          # security(JWT/bcrypt) / deps(鉴权/RBAC)
│       ├── middleware/                    # trace 中间件
│       ├── models/                        # SQLAlchemy: user/kb/document/conversation
│       ├── schemas/                       # Pydantic 出入参
│       ├── db/                            # 异步引擎与会话
│       └── services/                      # 核心: rag / channel / vector_store /
│                                          #       embedding / rerank / llm / memory /
│                                          #       document / kb
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx / main.tsx             # 路由与入口
        ├── api/client.ts                  # axios 封装
        ├── stores/authStore.ts            # zustand 登录态
        ├── components/MainLayout.tsx      # 后台布局
        └── pages/                         # Login / Dashboard / KnowledgeBase /
                                           # Documents / QAChat
```

---

## 🗺️ 路线图与当前状态

> 当前版本 **v0.9**，覆盖 PRD 的 P0 主链路（双通道问答、知识库与文档管理、双层权限、混合检索+Rerank、引用与拒答、会话记忆、OpenAI 兼容 API、管理端 UI）。

- ✅ **已完成（MVP）**：双通道配置与差异化检索、JWT 认证 + RBAC、文档上传入库、混合检索 + Rerank + 置信拒答 + 引用后校验、SSE 流式与 OpenAI 兼容端点、React 管理端
- 🚧 **进行中 / 规划（P1+）**：Celery Worker 完全异步入库与进度回推、评测集与发布门禁、内容安全审核（对客）、转人工工单对接、查询改写/指代消解、Qdrant 生产部署与容量压测、GraphRAG / Agent 工具化（P2）

详见技术方案 §14《实施计划与演进路线》。

---

## 🙏 致谢

- 参考并生产化了 [RagLangChainTest](https://github.com/NanGePlus/RagLangchainTest)（RAG + LangChain + FastAPI 教学示例）的 LCEL 检索链、Re-ranker、对话记忆、PDF 表格预处理等能力。
- 模型能力由 [阿里云百炼 · 通义千问](https://bailian.console.aliyun.com/) 提供。

---

## 📄 License

本项目基于 [MIT License](LICENSE) 开源。
