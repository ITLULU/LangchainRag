# 智汇 · 企业级 RAG 知识库平台（AskKB）技术方案

## 1. 文档信息

| 文档信息 | 内容 |
|---|---|
| 方案名称 | 智汇 · 企业级 RAG 知识库平台技术方案（代号 AskKB） |
| 文档版本 | v0.9（评审稿） |
| 编制角色 | 技术总监 / 企业架构师 |
| 编写日期 | 2026-10-04 |
| 关联 PRD | `AskKB-企业级RAG知识库-PRD.md` v0.9（评审稿） |
| 目标仓库 | `E:/project/LangchainRag`（LangChain + FastAPI 技术栈新建工程） |
| 对标基准 | 参考项目 `RagLangChainTest`（LCEL+FastAPI+SSE、Chroma 灌库、Reranker、对话记忆、PDF 表格预处理）的企业级架构升级 |
| 强制约束 | 模型层锁定阿里云百炼（qwen-plus 生成 + text-embedding-v4 向量化 + qwen3-rerank 精排），数据不出境 |

> **本方案核心贯穿概念——双通道（Dual-Channel）**：一套知识库底座，两类检索/问答通道。
> - **通道 A `employee_kb`（企业员工手册）**：面向内部员工，重权限、重溯源、密级过滤。
> - **通道 B `cs_agent`（智能客服问答）**：面向 C 端客户，高并发、重体验、强制内容审核 + 转人工兜底、永远屏蔽内部/机密知识。
>
> 通道是一级配置维度，驱动「有权 collection 集合、Prompt 模板、密级过滤规则、限流阈值、内容审核开关、转人工策略、模型参数」全套差异化行为（详见 §6.1、§7）。

---

## 2. 概述与需求对齐

### 2.1 背景

引用 PRD 结论：企业万级文档知识散落、AI「读不懂也找不到」；RAG 工程化成熟 + 百炼按量计费提供低成本入场窗口。需在 `LangchainRag` 仓库内，以 `RagLangChainTest` 已验证的 LangChain 链路为技术基线，构建可运营、带权限隔离、质量可度量的企业级 RAG 平台，同时服务「对客智能客服」与「对内员工知识」两类场景。

### 2.2 技术目标（直接引用 PRD 指标）

| 目标维度 | 指标值 | 来源 |
|---|---|---|
| 对客首字延迟 | ≤ 3s（P95） | PRD NFR-性能 / 成功指标 |
| 对客端到端 | ≤ 8s（P95） | PRD NFR-性能 |
| 检索耗时（不含生成） | ≤ 500ms（P95） | PRD NFR-性能 |
| 并发能力 | 对客 200 并发 / 对内 50 并发 | PRD NFR-性能 |
| 服务可用性 | 核心问答 SLA 99.9%（月） | PRD NFR-可用性 |
| 越权检索事故 | 0（双层过滤硬保证） | PRD BR-3 / 风控指标 |
| 引用覆盖率 | 100% | PRD FR-3.5 / BR-5 |
| 单次问答综合成本 | ≤ 0.05 元 | PRD NFR-成本 |
| 容量 | 10 万级文档 / 500 万级切片 / collection ≥ 200 | PRD NFR-可扩展 |

### 2.3 方案范围与红线

- **做**：知识库与文档管理、异步入库流水线、混合检索 + Rerank + 引用 + 拒答、**双层权限过滤**、**对客/对内双通道问答 API**、会话记忆、审计、评测门禁、监控告警、客服转人工与反馈闭环。
- **不做（对齐 PRD MVP 红线）**：GraphRAG、Agent 编排、多语言、图片/音视频知识、自训练/微调模型、移动端 Native、工单系统本体、全私有化模型部署、多租户 SaaS。均以「可插拔预留扩展点」方式承接，不进入本期开发排期。

### 2.4 与 PRD 对应关系

本方案逐条覆盖 PRD 全部 **FR（7 模块 40 项）/ BR（14 条）/ NFR（7 类）**。追溯映射见附录 A《PRD 指标与需求对照表》，编号交叉引用格式 `FR-x.x → §章节`。

---

## 3. 需求理解与技术分析

### 3.1 FR → 技术影响（关键项）

| 类型 | 编号 | 需求摘要 | 技术影响 / 应对思路 |
|---|---|---|---|
| FR | 1.1 知识库=collection | 每 KB 绑定 collection | KB 元数据表存 `collection_name`，创建 KB 触发 Qdrant collection 建立；通道类型 `channel_type` 为 KB 一级属性 |
| FR | 1.2/2.1 上传即异步 | 多格式 + 不阻塞 | 上传入 OSS + 建 `ingest_task`，Celery Worker 消费；API 立即返回 task_id |
| FR | 1.4/BR-7 版本覆盖 | 先建新后删旧 | 版本指针 `current_version` 原子切换 + 旧 `doc_version` 向量按 filter 删除（Saga 式补偿） |
| FR | 1.7 切分策略可配 | 中/英双策略 | 迁移参考项目 `pdfSplitTest_Ch/En` 为策略类，KB 级配置 chunk_size/overlap/分隔符 |
| FR | 1.8 PDF 表格 | 两种方案 | 方案①qwen-vl 摘要；方案②LLM 表格转自然语言；KB 级开关，Worker 内执行 |
| FR | 2.4 切片 metadata | 权限+溯源字段 | 每 chunk 写入 kb_id/doc_id/doc_version/security_level/department/page_no 等，双层过滤依赖 |
| FR | 3.2 混合检索 | 向量 + BM25 + RRF | 向量召回 topN=20 + 关键词召回（Qdrant match / ES），RRF 融合后送 Rerank |
| FR | 3.3 Rerank | 精排出置信度 | qwen3-rerank 精排取 top5，max score 作为 confidence 输入 BR-6 |
| FR | 3.4/BR-3 权限过滤 | 双层强制 | ①有权 KB → collection 白名单；②查询强制注入 `security_level ≤ 用户上限` + 部门 filter |
| FR | 3.5/BR-5 引用+拒答 | 必有引用、低置信拒答 | Prompt 约束 + 输出后校验（无引用即判拒答），confidence < 阈值走拒答/转人工分支 |
| FR | 3.7 对话记忆 | Redis 会话 | `conversation_id` → Redis（TTL 24h），拼接最近 5 轮 |
| FR | 4.5 通道隔离 | 双通道独立配置 | ChannelConfig 配置对象：检索/模型/Prompt/限流/审核/转人工按 channel 解析（§6.1） |
| FR | 6.2/BR-12 评测门禁 | 变更须过评测 | 评测服务 + 发布流水线卡点，报告不达标阻断发布（写库版本号不切换） |

### 3.2 NFR → 技术约束

| NFR | 目标 | 技术约束/手段 |
|---|---|---|
| 性能 | 首字 ≤ 3s、端到端 ≤ 8s | 全链路异步（FastAPI+asyncio）、SSE 流式先出首 token、多 collection 并行检索、连接池复用、Embedding/Rerank 超时熔断 |
| 可用性 99.9% | 百炼故障降级 | 模型抽象层多渠道热切换（主百炼 → 备 OneAPI 网关 → 仅返回检索原文），向量库故障快速失败禁生成 |
| 可扩展 | 10 倍容量余量 | API 无状态（会话/任务外置 Redis/DB）多实例负载；向量库 Repository 抽象，Qdrant→Milvus 可迁移 |
| 安全合规 | 数据不出境、Key 不落地 | 仅境内百炼；Key 走配置中心/环境变量；PII 双向脱敏；审计 ≥ 180 天 |
| 成本 | ≤ 0.05 元/次 | 真实计费测算（§12）；预算上限+超额降级（关 Rerank/减 topK） |

### 3.3 BR → 技术规则（可配置化落点）

| BR | 规则要点 | 技术落地 |
|---|---|---|
| BR-1 | 入库 ≤ 10 分钟 + 超时重试 ≤ 2 | Celery 任务超时监控 + 自动重试计数 |
| BR-2 | > 50MB/> 500页/> 100文件拒绝 | 上传网关前置校验器 |
| BR-3 | 双层权限过滤强制 | 检索管道 `PermissionFilterInjector` 硬编码不可关闭，缺一层判安全缺陷 |
| BR-4 | 对客永不召回内部/机密 | `cs_agent` 通道 metadata 强制 `security_level == 公开` |
| BR-6 | confidence=max(rerank)；切片<2 打 8 折；默认阈值 0.35 | ConfidenceScorer 策略类，阈值 KB 级可覆写、下调需审批留痕 |
| BR-8 | 失效期检索排除不删除 | metadata `expiry` 过滤 + 定时任务标记；90 天后可归档 |
| BR-9 | 记忆 TTL 24h / C端会话 90天 / 审计 180天 | Redis TTL + 数据生命周期清理任务 |
| BR-10 | 限流 20 次/分 + 对客熔断错误率>10% | Redis 令牌桶 + 熔断器（5 分钟窗口） |
| BR-12 | 三类变更须过评测方可发布 | 发布状态机：draft→(评测通过)→online |
| BR-13 | 离职/禁用 ≤ 5 分钟失效 | JWT 短过期 + Redis 黑名单，IdP 同步推送 |

---

## 4. 总体架构设计

### 4.1 架构原则

1. **双通道优先分离**：通道差异收敛到 ChannelConfig，业务链路对 channel 无硬编码分支，新增通道只加配置。
2. **安全默认（Secure by Default）**：权限双层过滤为管道强制环节，默认拒答、默认脱敏、默认审计。
3. **异步与无状态**：重 IO（入库/评测/审计写）全异步，API 无状态可水平扩展，状态外置 Redis/MySQL。
4. **可插拔演进**：向量库、Reranker、模型渠道均为接口实现，容量增长或供应商变更不改业务代码。
5. **故障隔离与降级**：模型/向量库/审核各自熔断降级，最坏情况「只读检索原文、禁无依据生成」，绝不静默返回错误答案。

### 4.2 分层逻辑架构

```
┌───────────────────────────────── 接入层 ─────────────────────────────────┐
│ 通道B:官网/APP/公众号 SDK   通道A:企业内部门户   管理端Web   OpenAI兼容API  │
│   网关(APIGateway): JWT鉴权 → 解析channel → RBAC → 限流/熔断 → trace_id     │
└───────────────────────────────────┬──────────────────────────────────────┘
┌────────────────────── 应用层（FastAPI 服务，无状态，多实例） ──────────────┐
│  ┌── 问答编排(QaOrchestrator, LCEL Chain) ──┐  ┌── 知识库/文档管理服务 ──┐  │
│  │ 通道解析→query改写→权限注入→混合检索→      │  │ KB CRUD / 上传 / 版本 /  │ │
│  │ Rerank→置信判定→生成(引用)→校验→审核→落审计│  │ 切分预览 / 元数据         │ │
│  └──────────────────────────────────────────┘  └─────────────────────────┘  │
│  会话记忆服务(Redis)  权限解析服务(RBAC)  评测门禁服务  审计服务  转人工服务 │
└───────────────┬──────────────────────────┬────────────────────┬──────────┘
┌──────────── 异步任务层（Celery Worker + Beat） ───────────────┐
│ 入库流水线(解析→切分→Embedding→写向量库)  重建索引  定时(失效下线/归档/评测)  │
└───────────────┬───────────────────────────────────────────────┘
┌──────────── 模型层（阿里云百炼，OpenAI 兼容协议 + 抽象适配） ──┐
│ qwen-plus(生成)  text-embedding-v4(向量化)  qwen3-rerank(精排)             │
│ qwen-vl(表格图片摘要)  内容安全审核API(仅通道B)  备用渠道(OneAPI网关)        │
└───────────────────────────────┬───────────────────────────────┘
┌──────────────────────────── 数据层 ──────────────────────────────────────┐
│ 向量库: Qdrant(生产,每KB一collection) / Chroma(dev)  ← Repository 抽象     │
│ 元数据/权限/审计/任务/评测: MySQL   会话/限流/队列: Redis   原始文件: OSS/MinIO│
└───────────────────────────────────────────────────────────────────────────┘
```

### 4.3 部署架构

```
                     [CDN / SLB 负载均衡]
                              │
             ┌────────────────┴────────────────┐
             │  API 服务节点 ×2 (4C8G, FastAPI) │  无状态，可横向扩容
             └───────┬────────────────┬────────┘
                     │                │
        [Celery Worker ×2]     [Redis 主从 / Sentinel]
        (入库/评测任务)          会话·限流·队列·缓存
                     │
   ┌─────────────────┼──────────────────┬───────────────┐
   │                 │                  │               │
[MySQL 主备]     [Qdrant 集群/单节点]  [OSS/MinIO]   [百炼 API(公网,内网出口)]
元数据·权限·审计  向量 collection      原始文档
```

- **网络分区**：接入区（SLB+API，DMZ）／应用区（Worker、Redis、MySQL、Qdrant，内网）／模型出口（唯一经百炼网关出公网，其余无出域）。
- **环境**：dev（Chroma + 本地 MinIO + 单机 Redis）/ test（镜像生产拓扑）/ prod（Qdrant + OSS + Redis 主从 + MySQL 主备）。
- **交付形态**：Docker Compose 一键起（对齐 PRD 可维护 NFR），生产可平滑迁 K8s。

### 4.4 关键组件清单

| 组件 | 职责 | 运行形态 |
|---|---|---|
| APIGateway（FastAPI 中间件层） | JWT 鉴权、channel 解析、RBAC、限流熔断、trace_id 注入 | 随 API 进程 |
| QaOrchestrator | LCEL 问答链路编排（双通道差异化装配） | API 进程内 |
| KnowledgeService | KB/文档/版本/元数据/切分预览管理 | API 进程内 |
| PermissionService | 用户有权 KB 解析、密级映射、双层过滤表达式生成 | API 进程内 + Redis 缓存 |
| IngestionWorker | 解析→切分→Embedding→写库→自检 | Celery Worker |
| RetrievalRepository | 向量/关键词检索统一接口（Qdrant/Chroma 适配） | 库 + 远程向量库 |
| ModelAdapter | 百炼/OneAPI 统一 OpenAI 兼容封装 + 多渠道降级 | HTTP 客户端 |
| EvalService | 评测集跑批、门禁判定、报告 | Celery 任务 + API |
| AuditService | 问答/操作/权限变更审计写（追加不可改） | 异步写 MySQL |
| HandoffService | 通道 B 转人工（对接坐席/工单系统） | API + 回调 |

---

## 5. 技术选型

| 领域 | 候选方案 | 选型结论 | 理由与拒绝项 |
|---|---|---|---|
| Web 框架 | FastAPI / Flask / Spring Boot | **FastAPI** | 原生 asyncio + SSE 流式 + Pydantic 校验，延续 RagLangChainTest 已验证路径；拒绝 Flask（无原生异步流式）、Spring Boot（Python 生态模型/向量库 SDK 更契合，PRD 定位 LangChain 工程） |
| RAG 框架 | LangChain(LCEL) / LlamaIndex / 自研 | **LangChain LCEL** | 参考项目已用 LCEL chain，组件齐全（retriever/prompt/并行/重试），拒绝自研（重造轮子、无社区）；LlamaIndex 团队不熟、迁移成本高 |
| LLM | 百炼 qwen-plus / qwen-max / GPT 系 | **qwen-plus（主）** | 中文质量与成本平衡，境内合规（拒绝 GPT：数据出境风险 PRD NFR）；qwen-max 成本高一倍留作复杂问答升级；PRD 已锁 qwen-plus |
| Embedding | text-embedding-v4 / v1 / v3 / 本地 bge | **text-embedding-v4** | 0.5 元/百万 token、1024 维、中文召回优、支持 batch=10；拒绝 v1（参考项目用的旧版，召回与额度弱）；本地 bge 需 GPU 运维，PRD 红线不做私有化 |
| Reranker | qwen3-rerank / gte-rerank-v2 / 本地 bge-reranker | **qwen3-rerank（主）** | 0.5 元/百万 < gte-rerank-v2 0.8 元，效果更优；本地 bge-reranker-large 作离线/降级备选（参考项目已跑通），拒绝常态本地（占用 API 节点资源） |
| 向量库 | Qdrant / Milvus / Chroma / Redis | **Qdrant（生产）+ Chroma（dev）** | Qdrant payload 过滤强、collection 隔离、轻量可单机可集群、Python 原生 client，契合「每 KB 一 collection + metadata 双层过滤」；Chroma 延续参考项目做本地开发；拒绝 Milvus（P0 运维重、无专职 DBA）作演进项；Redis 容量与过滤能力弱不选 |
| 元数据库 | MySQL / PostgreSQL | **MySQL 8** | 企业存量技术栈复用（工作区多项目用 MySQL），权限/审计/任务结构化数据足够 |
| 缓存/队列 | Redis + Celery / RabbitMQ + Kafka | **Redis + Celery** | 会话记忆、限流令牌桶、任务队列、进度共享一栈解决，运维简单；Kafka 对本场景过重（拒绝，PRD 无流式大数据需求） |
| 关键词检索 | Qdrant 内置 / Elasticsearch / BM25-python | **Qdrant match + 轻量 BM25** | 复用向量库减少组件；混合检索 RRF 融合；拒绝独立 ES（P0 增运维，列为 P1 演进项） |
| 对象存储 | 阿里云 OSS / MinIO | **OSS（生产）/ MinIO（私有化/测试）** | 与百炼同云降低传输与合规成本；PRD 允许私有化留白用 MinIO |
| API 网关 | 自研中间件 / Kong / Spring Cloud Gateway | **FastAPI 中间件（MVP）** | 单体网关足够（鉴权/限流/trace），拒绝引入独立网关组件（增加运维）；规模化后演进 |
| 可观测 | LangSmith / Prometheus+Grafana+OTel | **Prometheus+Grafana+结构化日志(OTel trace)** | 生产级指标四黄金信号 + AI 专项；LangSmith 用于 dev 调优链路跟踪（参考项目已验证），不进生产常态 |
| 内容审核 | 百炼/阿里云绿网内容安全 API | **阿里云内容安全（通道 B）** | 境内合规、与百炼同生态；通道 A 可关 |

---

## 6. 核心模块设计

### 6.1 模块划分与双通道装配

| 模块 | 职责 | 关键类/组件 | 依赖 |
|---|---|---|---|
| 通道配置模块 | 定义 channel → 差异化行为映射 | `ChannelConfig`、`ChannelResolver` | PermissionService |
| 知识库管理 | KB/文档/版本/元数据 CRUD、切分预览 | `KnowledgeService`、`ChunkPreviewService` | RetrievalRepository、OSS |
| 入库流水线 | 解析→切分→Embedding→写库→自检 | `IngestionWorker`、`DocumentParser`、`SplitStrategy(中/英)`、`PdfTableHandler` | Celery、ModelAdapter、RetrievalRepository |
| 问答编排 | LCEL 链路装配与执行（双通道） | `QaOrchestrator`、`RagChain` | Retrieval、ModelAdapter、MemoryService |
| 检索模块 | 混合召回 + Rerank + 权限过滤注入 | `HybridRetriever`、`RerankService`、`PermissionFilterInjector` | RetrievalRepository |
| 权限模块 | 有权 KB 解析、密级映射、双层过滤 | `PermissionService`、`SecurityLevelPolicy` | MySQL、Redis 缓存 |
| 记忆/改写 | 会话上下文 + query 指代消解 | `MemoryService`、`QueryRewriter` | Redis、ModelAdapter |
| 置信/拒答/转人工 | confidence 计算 + 分支路由 | `ConfidenceScorer`、`RefusePolicy`、`HandoffService` | ChannelConfig |
| 评测门禁 | 评测集跑批 + 发布卡点 | `EvalService`、`ReleaseGate` | Celery、MySQL |
| 审计 | 问答/操作/权限留痕 | `AuditService` | MySQL（追加写） |

**ChannelConfig 差异化配置示例（逻辑，非最终代码）**：

| 配置项 | `employee_kb`（通道A 员工手册） | `cs_agent`（通道B 智能客服） |
|---|---|---|
| 有权 collection 来源 | 用户部门/角色/密级映射的动态 KB 集合 | 仅 `channel_type=cs_agent & security_level=公开` 的 KB |
| 密级上限 | 用户密级（可含内部/机密） | 强制「公开」（BR-4 硬过滤） |
| Prompt 模板 | 内部知识助手模板（可展示推理与多源） | 对客话术模板（简洁、无内部术语、引导转人工） |
| 检索 topK / 阈值 | topK=5 / 拒答阈值 0.35 | topK=3（更快）/ 拒答阈值更高(如 0.45，宁可不答) |
| 并发限流 | 20 次/分/用户，50 总并发 | 20 次/分/客户，200 总并发 + 全局熔断 |
| 内容审核 | 关闭 | 强制开启（出口审核） |
| 拒答后动作 | 提示换问法 / 联系部门管理员 | 转人工（携带会话上下文） |
| 模型参数 | qwen-plus，temperature 稍高可总结 | qwen-plus，temperature≈0 求稳 |

### 6.2 问答编排链路（QaOrchestrator，对应 main.py LCEL 升级）

参考项目链路：`{query, context=retriever} | prompt | getPrompt | model`。本方案在生产化上扩展为完整 RunnableSequence/并行分支：

```
input(user_id, channel, question, conversation_id)
  → resolve_channel_config            # ChannelResolver（读取 ChannelConfig）
  → load_memory                        # MemoryService（Redis，最近5轮）
  → rewrite_query                      # QueryRewriter（指代消解，多轮才触发）
  → resolve_collections + build_filter # PermissionService（①collection白名单 ②密级/部门 filter）
  → hybrid_retrieve (parallel)         # HybridRetriever：多collection向量topN + BM25，RRF融合
  → rerank                             # RerankService（qwen3-rerank → topK）
  → score_confidence                   # ConfidenceScorer（BR-6）
  → branch:
       low_conf → (cs_agent? handoff : refuse)  # 拒答/转人工，不进LLM
       ok       → build_prompt(context,history,citation_rules)
                 → llm_generate (stream)         # qwen-plus SSE
                 → validate_citations            # 引用后校验(BR-5)，无引用→拒答
                 → content_moderation (cs_agent) # 内容审核
                 → emit answer + citations
  → async audit_write                  # AuditService（用户/channel/命中collection/引用/置信/耗时）
```

- 全程 asyncio，检索多 collection **并行**（LCEL `RunnableParallel`）降低时延；任一环节超时走降级（§7.3）。

### 6.3 入库流水线模块（对应 vectorSaveTest.py 升级）

`IngestionWorker` 将参考项目脚本式灌库升级为带任务状态、metadata、幂等、限流、自检的生产链路（详见 §7.2）。核心差异：MyVectorDBConnector 收敛为 `RetrievalRepository.add_chunks(kb_id, chunks_with_metadata)`，写入 Qdrant 对应 collection，ID = `doc_id:version:chunk_index` 保证幂等去重。

### 6.4 权限模块（本期核心，双层过滤实现）

- **第一层 collection 白名单**：`PermissionService.allowed_kbs(user)` → KB 列表 → collection 名集合，检索只在白名单内进行。缓存 Redis（用户权限 TTL 5 分钟 + 变更主动失效，满足 BR-13）。
- **第二层 metadata filter**：查询构造时强制 `must: security_level ∈ 用户允许密级, department ∈ 用户可见部门`；`cs_agent` 通道额外硬注入 `security_level == 公开`。
- `PermissionFilterInjector` 为管道必经节点，代码层面不可被业务跳过（缺失即抛异常，对应 BR-3「视为安全缺陷」）。

### 6.5 评测门禁模块

`EvalService` 跑评测集（每 KB ≥ 50 条），产出准确率/引用覆盖率/拒答准确率/幻觉抽检；`ReleaseGate` 对比当前线上版本指标，低于则阻断发布（Prompt/切分/检索参数/模型四类变更适用，BR-12）。

---

## 7. 关键流程设计

### 7.1 问答流水线（双通道时序）

```
客户/员工 → SLB → APIGateway(JWT校验, 解析channel)
  → QaOrchestrator:
      [通道B] 限流检查(20/min) → 熔断状态检查
      ChannelResolver → MemoryService(取会话) → QueryRewriter
      PermissionService(allowed_kbs + filter)   ← 通道B强制公开密级
      HybridRetriever(并行多collection召回 topN=20)
      RerankService(qwen3-rerank → topK)
      ConfidenceScorer
        ├ 低置信: [B]HandoffService(转人工,带上下文) / [A]RefusePolicy(拒答话术) → 审计 → 返回
        └ 正常:   build_prompt → qwen-plus SSE 流式生成
                  validate_citations(无引用→降级拒答)
                  [B]ContentModeration(绿网审核, 命中→替换/拦截)
                  流式返回 (chunk + 末尾 citations)
      async 写 query_log + audit_log（PII 脱敏）
```

异常分支：模型超时→§7.3 降级；审核命中违规→拒答/人工；引用缺失→拒答（绝不返回无依据答案）。

### 7.2 入库流水线（离线文档上传）

```
管理端/员工(有权) → 上传接口 → 校验(BR-2: 大小/页数/批量数)
  → 存 OSS(生成 file_key) → 建 ingest_task(QUEUED) → 立即返回 task_id
Celery Worker 消费:
  解析(DocumentParser: PDF/Word/PPT/Excel/MD/HTML)
  → [含表格KB] PdfTableHandler(方案①qwen-vl摘要 / 方案②LLM转自然语言)
  → SplitStrategy(KB配置: 中文段落/英文句子/固定长度+overlap) → chunks
  → 批量 Embedding(text-embedding-v4, batch=10, 令牌桶限流, 重试≤3退避)
  → RetrievalRepository.add_chunks(kb_collection, chunks + 权限/溯源metadata)
  → 更新 MySQL 状态(SUCCESS/FAILED, 进度%, 切片数, 耗时)
  → 自检(FR-2.5: 抽3句回检是否Top5, 不达标标记"索引质量预警", 不阻断)
版本更新: 新version入库成功 → 原子切 current_version → 删旧version切片(BR-7, 删失败回滚指针)
定时任务(Beat): 扫描 expiry 到期 → 检索层标记排除(BR-8) → 90天后归档
```

### 7.3 异常与降级流程

| 故障 | 检测 | 降级动作 |
|---|---|---|
| 百炼 qwen-plus 5xx/超时 | ModelAdapter 错误率 + 超时 | 熔断 30s → 切备用 OneAPI 渠道 → 仍失败则**返回检索原文片段 + 「智能回答暂不可用」提示**（通道 B 直接转人工），禁无依据生成 |
| text-embedding 失败 | 入库任务重试 | ≤3 退避；持续失败标 FAILED，不写脏向量 |
| qwen3-rerank 失败 | 调用超时 | 跳过精排，用向量相似度分数（confidence 相应保守，倾向拒答）；或切本地 bge-reranker |
| Qdrant 不可用 | 健康检查 | 问答接口快速失败 + 告警，**禁止降级为纯 LLM 作答**（违反 BR-5）；管理端只读 |
| 内容审核服务超时（通道B） | 审核调用超时 | 保守策略：命中未判定 → 转人工/拒答，不放行未审核内容 |
| 全局错误率 > 10%（通道B，5min） | 熔断器 | 开启熔断，仅返回「转人工」兜底（BR-10） |

---

## 8. 数据设计

### 8.1 核心实体与关系（ER 要点）

```
knowledge_base (kb_id PK, name, channel_type[employee_kb|cs_agent], collection_name,
                owner_dept, visibility[public|dept|role], chunk_strategy, table_strategy,
                reject_threshold, status, created_by, created_at)
        │ 1:N
document (doc_id PK, kb_id FK, title, author, dept, security_level[公开|内部|机密],
          effective_date, expiry_date, tags, current_version, status, created_at)
        │ 1:N
doc_version (doc_id+version PK, oss_file_key, file_type, size, page_count, index_status,
             chunk_count, error_msg, created_at)
        │ 1:N   (向量本体在 Qdrant，MySQL 存切片元信息用于删除/审计对齐)
chunk_meta (chunk_id PK=doc_id:ver:idx, doc_id, version, chunk_index, page_no,
            token_len, vector_id)
kb_grant (kb_id, grantee_type[dept|role|user], grantee_id, can_read)   ← 第一层过滤
role / user_role / user_security_level                                  ← RBAC
ingest_task (task_id PK, doc_id, status, progress, chunk_count, cost_ms, error, retry_cnt)
conversation (conv_id PK, channel, user_id, external_uid_masked, created_at, expire_at)
message (msg_id PK, conv_id FK, role, content_masked, created_at)       ← 冷数据落MySQL, 热在Redis
query_log (log_id PK, trace_id, user_id, channel, kb_ids, collection_hits,
           citations, confidence, refused, handoff, latency_ms, cost, created_at)
feedback (fb_id, query_log_id, rating[up|down], reason)                 ← BR-11
audit_log (audit_id, actor, action, target, before, after, hash_chain, created_at) ← 不可篡改
eval_set (kb_id, question, expect_doc, expect_points)
eval_run (run_id, kb_id, version_snapshot, accuracy, citation_cov, refuse_acc, pass, report)
```

### 8.2 存储选型表

| 数据 | 存储介质 | 理由 |
|---|---|---|
| KB/文档/版本/权限/任务/评测 | MySQL | 强一致结构化关系数据，事务与关联查询 |
| 向量 + 可过滤 metadata | Qdrant（每 KB 一 collection） | 向量 ANN + payload filter 一体化，支撑双层过滤 |
| 切片文本正文 | Qdrant payload（可回溯） + OSS 原件 | 溯源展示用；原件保留可重建索引 |
| 会话记忆/限流计数/队列/权限缓存 | Redis | 低读写延迟、TTL 天然适配 BR-9/10/13 |
| 原始文档 | OSS / MinIO | 大对象、版本化、生命周期规则 |
| 审计/问答日志 | MySQL（audit_log 哈希链） | 可查询、不可篡改 |

### 8.3 缓存策略与一致性

- **权限缓存**：`user → allowed_kbs` Redis 缓存 TTL 5 分钟；权限/离职变更主动删除键（满足 BR-13 ≤ 5 分钟）。
- **会话缓存**：`conv_id → 最近5轮` Redis，TTL 24h（BR-9）；异步落 MySQL 冷存。
- **写后一致性（向量 vs 元数据）**：入库以 Worker 任务串行「先写 Qdrant 成功 → 再更新 MySQL 状态」；删除/版本切换采用 **先建新后删旧 + 失败回滚版本指针**（BR-7），避免新旧并存或误删。
- **热点问答缓存**（成本优化）：高频完全相同问题命中缓存直接返回（命中判断走归一化 query），降低模型调用（见 §12）。

### 8.4 数据生命周期

| 数据 | 保留 | 处理 |
|---|---|---|
| 会话记忆 | 无活动 24h 过期（Redis TTL） | BR-9 |
| C 端会话内容 | 90 天后清理 | 定时任务删除 |
| 审计日志 | ≥ 180 天 | 追加写不可删改，到期归档对象存储 |
| 文档版本 | 保留最近 3 版 | 超出的历史版本向量清理 |
| 失效文档 | 检索排除不删除，失效 90 天后可归档 | BR-8 |
| PII | 入库/日志双向脱敏后存储 | §11 |

---

## 9. 接口设计

### 9.1 接口规范

- **认证**：`Authorization: Bearer <JWT>`；`/v1/chat/completions` 与 `/api/*` 全部要求鉴权，匿名一律 401（FR-4.1）。JWT 携带 `user_id / channel_scope / security_level / dept`。
- **通道标识**：问答接口通过 `channel` 字段或访问端点绑定解析；管理接口按 RBAC 权限点校验。
- **分页**：列表统一 `page`/`page_size`（默认 20，≤ 100），返回 `total`。
- **幂等**：写操作支持 `Idempotency-Key` 头；上传以 `(doc_id, version)` 幂等。
- **错误码体系**：`{code, message, trace_id, detail}`；业务码分域（1xxx 鉴权权限 / 2xxx 文档入库 / 3xxx 问答 / 4xxx 评测）。

### 9.2 API 详表

| 方法 | 路径 | 简述 | 对应 FR |
|---|---|---|---|
| POST | /v1/chat/completions | OpenAI 兼容问答（流式/非流式），body 带 channel | FR-3.1 |
| POST | /api/ask | 简化问答 {question,conversation_id,kb_ids,channel} | FR-3.1 |
| GET | /api/conversations/{id}/messages | 会话历史 | FR-3.7 |
| POST | /api/kb | 创建知识库（含 channel_type、切分/表格策略） | FR-1.1 |
| GET | /api/kb | 知识库列表（按调用者权限过滤） | FR-4.3 |
| PUT | /api/kb/{kb_id} | 编辑/归档知识库 | FR-1.1 |
| POST | /api/kb/{kb_id}/documents | 批量上传（multipart，建入库任务） | FR-1.2 |
| GET | /api/documents | 文档列表与索引状态 | FR-1.3 |
| GET | /api/documents/{doc_id} | 文档详情/版本 | FR-1.3/1.4 |
| POST | /api/documents/{doc_id}/preview-split | 切分预览（切片+预估token） | FR-1.7 |
| PUT | /api/documents/{doc_id}/metadata | 元数据/密级/生效期 | FR-1.6/1.9 |
| DELETE | /api/documents/{doc_id} | 删除文档（联动向量清理） | FR-1.5 |
| POST | /api/documents/{doc_id}/reindex | 重建索引 | FR-1.4 |
| GET/PUT | /api/kb/{kb_id}/permissions | 知识库授权读写 | FR-4.3 |
| GET | /api/tasks/{task_id} | 入库任务进度 | FR-2.2 |
| POST | /api/eval/runs | 触发评测回归 | FR-6.2 |
| GET | /api/eval/runs/{id}/report | 评测报告 | FR-6.2 |
| POST | /api/feedback | 点赞/点踩反馈 | FR-5.4 |
| GET | /api/logs/queries | 问答日志检索（审计/质检） | FR-5.5/6.4 |
| GET | /api/dashboard/knowledge-ops | 知识运营看板数据 | FR-6.3 |

### 9.3 关键请求/响应示例（通道 B 问答）

```jsonc
// POST /api/ask
{ "channel":"cs_agent", "question":"这款机型支持7天无理由退货吗？",
  "conversation_id":"c_8f21", "external_uid_masked":"cust_****1234" }

// 200 (非流式)
{ "answer":"支持。自签收起 7 天内可申请无理由退货[1]。",
  "citations":[{"no":1,"doc":"售后政策V3.pdf","page":12,
                "snippet":"自签收起7日内可无理由退货...","score":0.62}],
  "confidence":0.62, "refused":false, "handoff":false, "trace_id":"..." }
// 低置信/敏感意图 → { "answer":"已为您转接人工客服","handoff":true,"refused":true }
```

### 9.4 版本策略

- 路径前缀 `/v1`；破坏性变更走 `/v2` 并保留 `/v1` 兼容期 ≥ 6 个月，废弃走 Deprecation 头 + 公告。OpenAI 兼容端点长期保持稳定协议。


---

## 10. 非功能需求落地（逐条 NFR）

| NFR | 目标 | 技术方案 | 验证方式 |
|---|---|---|---|
| 性能-首字 | 对客 ≤ 3s（P95） | asyncio 全链路 + SSE 先出首 token + 多 collection 并行检索 + HTTP 连接池复用 + qwen-plus 流式 | Locust 压测 200 并发，统计 P95 首字；灰度真实流量埋点 |
| 性能-端到端 | 对客 ≤ 8s / 对内 ≤ 10s（P95） | topK 精排裁剪、检索 ≤ 500ms、模型超时 6s 熔断 | 压测 + APM 链路 P95 报表 |
| 性能-检索 | 检索 ≤ 500ms（P95） | Qdrant HNSW 索引 + 单库 collection 缩小召回域 + 结果缓存 | 向量库基准测试（50 万切片 Recall@k / latency） |
| 并发 | 对客 200 / 对内 50 | API 无状态多实例（×2 起步）+ Worker 分离 + Redis 主从 | 阶梯加压至目标并发看错误率与延迟拐点 |
| 可用性 | SLA 99.9%/月 | 多渠道热切换 + 降级只读检索 + 熔断 + MySQL/Redis/Qdrant 主备 | 故障注入演练（杀百炼/向量库验证降级与禁生成） |
| 可扩展 | 10 万文档/500 万切片/collection≥200 | Qdrant 单机→集群演进 + Repository 抽象 + 分 collection 隔离 | 容量压测 10 倍数据规模；扩节点回归 |
| 安全合规 | 数据不出境/Key不落地/PII脱敏/审计180天 | 仅境内百炼 + 配置中心密钥 + 双向脱敏管道 + 哈希链审计（见 §11） | 代码扫描无硬编码密钥；渗透越权用例；日志脱敏抽检 |
| 兼容 | OpenAI 协议/Chrome·Edge最新2版/SSE移动WebView | 端点严格对齐 OpenAI schema + 前端现代浏览器 + SSE 兜底轮询 | 协议一致性用例 + 浏览器矩阵手测 |
| 可维护 | 结构化日志/trace_id/配置分环境/测试≥70%/Compose一键起 | OTel trace + Pydantic Settings 分环境 + 策略类可插拔 + pytest 覆盖率门禁 + docker-compose | CI 覆盖率报告 <70% 阻断 + Compose 冒烟 |
| 成本 | ≤ 0.05 元/次 | 真实计费测算(§12) + 热点缓存 + 超额自动降级(关Rerank/减topK) | query_log 汇总单均成本看板 + 预算告警 |

---

## 11. 安全设计

### 11.1 鉴权与授权

- **认证**：对接企业 IdP（OAuth2/OIDC，钉钉/企微）；无 IdP 用内置账号体系。JWT 短时（15 分钟）+ Refresh，禁用/离职经 Redis 黑名单 ≤ 5 分钟失效（BR-13）。
- **授权（RBAC）**：6 内置角色（平台管理员/知识管理员/部门管理员/内部员工/客服坐席/C端客户）+ 自定义；权限点覆盖 KB 读写、文档管理、问答、审计查询、评测发布。
- **库级授权落点（双层，核心）**：第一层 `kb_grant` 决定可访问 collection 白名单；第二层检索强制 `security_level ≤ 用户上限` + 部门 filter（`PermissionFilterInjector` 不可跳过，缺失抛异常）。C 端仅命中 `channel_type=cs_agent & 公开` KB。

### 11.2 数据加密与密钥管理

- 传输全链路 HTTPS/TLS；对内组件间内网 + 可选 mTLS。
- 百炼 API Key / DB 连接串**严禁硬编码**（针对参考项目反面案例），统一走配置中心/环境变量，支持轮转；启动做配置校验项（FR-4.6），缺 Key 直接 fail-fast。
- 静态存储：OSS 开启服务端加密；MySQL 敏感列（external_uid）加密存储。

### 11.3 脱敏实现

- **双向脱敏管道**：入库/日志前对手机号、身份证、银行卡等 PII 正则+NER 识别脱敏；出口按需还原或掩码。
- C 端 `external_uid` 以掩码/加密存库，审计与看板均脱敏展示；query_log 内容脱敏后落库（抽检 20 条全合规为验收）。

### 11.4 审计（不可篡改）

- `audit_log` 追加写 + **哈希链**（每条含前条 hash）防篡改删改；记录登录、文档增删改、权限变更、每次问答（用户/channel/命中 collection/引用/置信/耗时）。
- 保留 ≥ 180 天，到期归档 OSS 只读桶；审计员可按 trace_id 完整还原一次问答决策链（对齐 PRD 验收「任取一条可还原」）。

### 11.5 通道 B 专项（对客安全）

- 出口强制内容审核（阿里云内容安全/绿网）：涉政、辱骂、违规 → 拦截或替换为兜底话术。
- 敏感意图（投诉/退款）→ 直接转人工，不由 LLM 处置（FR-5.1）。
- Prompt 对客模板禁止输出内部术语与未授权字段。

### 11.6 合规映射

- 数据不出境：仅境内百炼 endpoint + 境内云资源；
- 个保法/最小必要：PII 脱敏、会话 90 天清理、授权最小化；
- 权限红线：双层过滤 + 越权渗透用例（≥30 条）全部拦截为上线门禁。

---

## 12. 容量规划与成本估算

### 12.1 流量模型测算

| 项 | 估算 | 口径 |
|---|---|---|
| 对客问答量 | 800 次/日（峰值时段集中） | PRD P1 基线，7×24 |
| 对内问答量 | 200 人 × 5 次/日 = 1000 次/日 | PRD Persona |
| 日均总问答 | ≈ 1800 次/日 | — |
| 峰值 QPS | 均值 ≈ 0.02；按 20× 峰谷系数 + 活动尖峰，设计峰值取 **5~10 QPS** | 长生成占连接，按并发而非纯 QPS 核算 |
| 并发连接 | 对客 200 + 对内 50 = 250 并发（PRD NFR） | SSE 长连接为主 |
| 节点数 | API 2×(4C8G) 起步支撑 250 并发（asyncio 高并发，压测验证后扩） | Worker 2× 分离 |

### 12.2 基础设施资源估算（生产起步）

| 组件 | 规格 | 数量 | 年成本估算 |
|---|---|---|---|
| API 服务 | 4C8G | 2 | ~1.4 万 |
| Celery Worker | 4C8G | 2 | ~1.4 万 |
| Redis（主从/Sentinel） | 2C4G × 3 | 1 组 | ~0.8 万 |
| MySQL 主备 | 4C8G | 1 组 | ~1.2 万 |
| Qdrant | 4C16G（500 万切片 1024 维 ≈ ~20GB 级） | 1（可扩集群） | ~1.2 万 |
| OSS 对象存储 | 10 万文档 ≈ 数百 GB | — | ~0.3 万 |
| SLB/NAT/带宽 | — | — | ~0.6 万 |
| **基础设施合计** | — | — | **≈ 6.9 万/年**（落 PRD 6~10 万区间） |

### 12.3 AI 模型调用成本（按已核实百炼真实计费）

计费单价（每百万 token，境内）：qwen-plus 输入 0.8 / 输出 2；text-embedding-v4 0.5；qwen3-rerank 0.5。

```
单次问答成本 = 生成 + 精排 + 查询向量化
生成  : 输入≈4000 token(模板+context 5×~600+history+query) → 4000×0.8/1e6 = 0.0032 元
        输出≈500 token → 500×2/1e6 = 0.001 元
精排  : 20 条×~400 token = 8000 token → 8000×0.5/1e6 = 0.004 元
向量化: 查询 ~30 token → ≈ 0.000015 元
————————————————————————————————————————
单次合计 ≈ 0.0082 元   （远低于 PRD 上限 0.05 元，约 16% 余量充足）
```

- **年生成本**：1800 次/日 × 0.0082 × 365 ≈ **0.54 万/年**。
- **入库一次性向量化**：假设 5 万文档 × 平均 3000 token = 1.5 亿 token × 0.5/1e6 ≈ **75 元**；重建索引按次，年度含重建预留 ≈ **0.1 万/年**。
- **模型调用年成本 ≈ 0.6~0.8 万/年**，显著低于 PRD 预算 5~8 万（PRD 按 0.05 元/百万级估算偏保守，实测单价更低）。
- **通道差异**：对客 topK=3、宁拒答，平均 context 更短，单均成本更低。

### 12.4 成本优化手段

1. **热点问答缓存**：高频相同/近似问题命中缓存直接返回，免检索与生成（预期再降 20~30%）。
2. **上下文裁剪**：context 精简（去重、摘要），控制输入 token。
3. **Batch 半价**：离线入库向量化用百炼 Batch 调用（半价）。
4. **分级模型**：简单 FAQ 走 qwen-turbo/flash，复杂问答才 qwen-plus。
5. **降级省费**：预算超限自动关 Rerank / 减 topK（对齐 NFR-成本）。
6. **topK 调优**：对客更激进（topK=3、高阈值），减少无效 token。

---

## 13. 运维与监控设计

### 13.1 部署与 CI/CD

- 环境：dev（Chroma+MinIO+单机Redis，docker-compose 一键起）/ test / prod。
- 流水线：Git → CI（lint + pytest 覆盖率≥70% 门禁 + 镜像构建）→ 部署 test → **评测门禁**（核心链路变更跑 EvalService，不达标阻断）→ 灰度 prod（按 channel/用户百分比）→ 全量。
- 配置：Pydantic Settings 分环境，密钥仅注入环境变量/配置中心，禁入库。

### 13.2 监控告警（SRE 四黄金 + AI 专项）

| 类别 | 指标 | 告警阈值 |
|---|---|---|
| 延迟 | 首字/端到端/检索 P95 | 端到端 > 8s（对客）持续 5min |
| 流量 | QPS/并发/按 channel 分布 | 突增 > 2× 基线 |
| 错误 | 问答失败率/拒答率/审核拦截率 | 失败率 > 10%（触发对客熔断）；拒答率突升（知识质量预警） |
| 饱和度 | CPU/内存/队列积压/连接池 | 队列积压 > 阈值 / Worker 饱和 |
| AI 专项 | 百炼调用错误率、配额余量、token 用量与成本、Rerank/embedding 时延、**阈值命中分布** | 配额 < 20% / 日成本超预算 / 错误率 > 5% |
| 基础设施 | Qdrant 可用、Redis、MySQL、向量库 collection 数 | 健康检查失败即告警 |

- 栈：Prometheus 采集 + Grafana 大盘（含「问答成本/自助解决率/零命中查询」业务盘）+ Alertmanager 推 IM。
- 链路：OTel/LangSmith trace_id 贯穿网关→检索→模型，异常可按 trace 还原。

### 13.3 日志与审计

- 结构化 JSON 日志（trace_id、channel、user 掩码、耗时、命中 collection、confidence）；
- 问答与操作审计独立入 audit_log（哈希链，见 §11.4），与运行日志分离，PII 脱敏。

### 13.4 备份与演练

| 对象 | 策略 | RTO/RPO |
|---|---|---|
| MySQL | 每日全量 + binlog 增量，保留 30 天 | RTO < 1h / RPO < 5min |
| Qdrant | collection 快照 + 原始文档可全量重建索引兜底 | 重建窗口目标 < 4h |
| OSS | 版本化 + 跨可用区冗余 | — |
| 配置/密钥 | 配置中心版本化 | — |

- 故障演练（季度）：杀百炼渠道验证降级禁生成、杀向量库验证快速失败与告警 ≤ 5min、越权渗透用例回归、主备切换。

---

## 14. 实施计划与演进路线

### 14.1 技术任务分解（对齐 PRD 里程碑）

| 里程碑 | 技术任务 | 关联 FR | 角色 |
|---|---|---|---|
| M0 预研(2周) | embedding v4 vs v1 召回对比、rerank 选型实测、Qdrant 50 万切片压测、基线数据采集、架构评审 | R1/R7/假设3 | 算法+架构 |
| M1 MVP(8周) | 项目骨架(FastAPI+MySQL+Redis+Qdrant+Celery)、KB/文档/版本管理、异步入库流水线(解析/切分/表格/自检)、混合检索+Rerank、双层权限、拒答+引用、双通道问答 API(SSE)、审计 | FR-1.x/2.x/3.x/4.x/6.4 | 后端2+检索1+前端1 |
| M2 质量治理(6周) | 评测集+回归门禁、转人工、反馈闭环、会话记忆+query改写完善、监控告警、运营看板 | FR-3.7/3.8/5.x/6.2/6.3/6.5 | 后端+算法 |
| M3 规模化(持续) | 全量部门铺开、知识治理专项、容量演进(Qdrant集群/Milvus评估)、GraphRAG·Agent 试点(P2) | FR-7.x | 全团队 |

### 14.2 演进路线

- **检索**：单路向量（参考项目）→ 混合 + Rerank（P0）→ 查询理解深化/多跳 GraphRAG（P2）。
- **向量库**：Chroma（dev）→ Qdrant 单节点（P0）→ Qdrant 集群 / 视规模迁 Milvus（Repository 抽象保障迁移）。
- **关键词**：Qdrant match + 轻量 BM25（P0）→ 独立 ES 检索（P1，若召回质量需强化）。
- **模型**：qwen-plus 单一（P0）→ 分级路由 + 上下文缓存（成本/质量演进）。
- **网关**：FastAPI 内建中间件（P0）→ 独立网关（规模化）。

### 14.3 技术风险登记

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| TR1 | 百炼配额/服务波动中断对客 | 中 | 高 | ModelAdapter 多渠道热切 + 降级只读检索 + 配额预警 |
| TR2 | 双层权限过滤有实现漏洞致越权 | 低 | 极高 | Injector 不可跳过 + 越权用例上线门禁 + 审计回溯 |
| TR3 | 切分/文档质量差致召回不达标 | 中 | 高 | 切分预览 + 入库自检 + 评测门禁 + 零命中治理闭环 |
| TR4 | 幻觉/无引用答案流入对客 | 中 | 高 | confidence 拒答 + 引用后校验 + 内容审核 + 转人工兜底 |
| TR5 | 成本失控（输出失控重试/尖峰/涨价） | 中 | 中 | 真实计费虽低，但需防异常重试/尖峰/调价；成本看板 + 预算告警降级 + 模型抽象层多供应商 |
| TR6 | Qdrant 后期迁移成本 | 低 | 中 | RetrievalRepository 抽象，M1 前压测定型 |
| TR7 | SSE 长连接并发压垮单实例 | 中 | 中 | 无状态多实例 + 连接池 + 压测扩容 + 超时回收 |
| TR8 | 版本切换/删除致向量脏数据 | 低 | 高 | 先建新后删旧 + 失败回滚指针 + doc_id 幂等 |

---

## 附录 A：PRD 指标与需求对照表

| PRD 编号/指标 | 本方案章节 | 验证方式 |
|---|---|---|
| 北极星·客服自助解决率≥60% | §6.1/§7.1 + 运营看板 | 上线后 query_log 统计 |
| 引用覆盖率 100%（FR-3.5/BR-5） | §6.2 validate_citations | 评测集 + 后校验强制 |
| 低置信拒答准确率≥90%（FR-3.6/BR-6） | §6.2 ConfidenceScorer | 20 条无答案用例 |
| 越权检索事故 0（FR-4.x/BR-3/4） | §6.4/§11.1 双层过滤 | ≥30 条越权渗透用例 |
| 首字≤3s/端到端≤8s（NFR性能） | §4/§6.2/§10 | 200 并发压测 P95 |
| SLA 99.9%（NFR可用） | §7.3/§13 | 故障注入演练 |
| 单次成本≤0.05 元（NFR成本） | §12.3 | 成本看板（实测≈0.008 元） |
| FR-1.x 知识库/文档/版本/切分/表格/失效 | §6.1/§7.2/§8.1 | 验收用例（PRD §13） |
| FR-2.x 异步入库/进度/限流/metadata/自检 | §7.2/§6.3 | 100页PDF≤10min + 幂等抽检 |
| FR-3.x 问答/混合检索/Rerank/记忆/改写/模板 | §6.2/§7.1 | 评测集 + 3轮指代命中 |
| FR-4.6 密钥不落地 | §11.2 | 代码扫描无硬编码 |
| FR-5.x 转人工/反馈/日志质检 | §6.1/§11.5/§13.3 | 4 类转人工触发验证 |
| FR-6.x 评测/看板/审计/监控 | §6.5/§13 | 门禁阻断 + trace 还原 |
| BR-1~BR-14 | §3.3/§7/§8/§11/§12 | 各规则专项用例 |

## 附录 B：技术假设待确认清单

1. **向量库**：假设 Qdrant 满足 10 万文档/500 万切片单机性能；M0 压测未达标则提前引入集群或评估 Milvus。
2. **Embedding**：假设 text-embedding-v4 在客户真实语料召回优于 v1（参考项目用 v1），M0 用评测集实测确认。
3. **认证**：假设企业有 IdP（OAuth2/OIDC）；若无则启用内置账号体系，增加组织/权限维护成本。
4. **计费**：本文成本按已核实百炼公开价（qwen-plus 0.8/2、embedding-v4 0.5、qwen3-rerank 0.5 元/百万 token）测算；实际以合同折扣/阶梯/免费额度为准，需财务复核。
5. **Rerank 选型**：默认 qwen3-rerank；若离线/降本需要，bge-reranker-large 本地部署需评估 API 节点 GPU/CPU 资源。
6. **拒答阈值 0.35**：经验起点，以 M1 评测集校准，通道 B 建议更高（宁转人工不答错）。
7. **对客渠道**：假设官网/APP/公众号已有会话承载页，本项目仅提供 API/SDK 与转人工对接接口，不含前端会话 UI。

## 附录 C：参考资料

- 关联 PRD：`AskKB-企业级RAG知识库-PRD.md` v0.9
- 参考架构：`RagLangChainTest`（main.py / mainReranker.py / mainMemory.py / vectorSaveTest.py / tools/pdfSplit*.py）
- 阿里云百炼模型与计费：模型广场 & 计费说明（qwen-plus、text-embedding-v4、qwen3-rerank/gte-rerank-v2 单价）
- LangChain LCEL / langchain-qdrant / langchain-community / FastAPI SSE 官方文档
