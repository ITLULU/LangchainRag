"""RAG 问答编排服务——核心链路：检索 → Rerank → 置信判定 → 生成 → 引用校验"""
import uuid
import time
import json
from typing import List, Dict, Optional, AsyncIterator
from dataclasses import dataclass, field

from langchain_core.documents import Document

from app.config import get_settings
from app.services.channel_service import channel_service, ChannelConfig
from app.services.vector_store import vector_store_service
from app.services.rerank_service import rerank_service
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from app.services.embedding_service import embedding_service

settings = get_settings()


@dataclass
class RetrievalResult:
    """单条检索结果"""
    chunk_id: str
    content: str
    score: float
    doc_title: str = ""
    page_no: int = 0
    doc_id: str = ""
    security_level: str = "公开"


@dataclass
class RAGResponse:
    """RAG 问答完整响应"""
    answer: str = ""
    citations: List[dict] = field(default_factory=list)
    confidence: float = 0.0
    refused: bool = False
    handoff: bool = False
    trace_id: str = ""
    conversation_id: str = ""
    latency_ms: int = 0
    used_collections: List[str] = field(default_factory=list)


class RAGService:
    """RAG 问答编排器——对应文档 6.2 节 QaOrchestrator"""

    async def ask(
        self,
        question: str,
        channel: str,
        user_id: str,
        user_security_level: str,
        user_department: str,
        conversation_id: Optional[str] = None,
        kb_ids: Optional[List[str]] = None,
        stream: bool = True,
    ):
        """
        执行完整的 RAG 问答链路

        流程：
        1. 通道配置解析
        2. 加载会话记忆
        3. 权限过滤（双层）
        4. 混合检索（多 collection 并行）
        5. Rerank 精排
        6. 置信度判定
        7. LLM 生成（流式/非流式）
        8. 引用校验
        9. 更新记忆
        10. 落审计日志
        """
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        conv_id = conversation_id or str(uuid.uuid4())

        config = channel_service.get_config(channel)

        # ── Step 1: 确定检索范围 ──
        permission_filter = channel_service.build_permission_filter(
            channel, user_security_level, user_department
        )

        # ── Step 2: 解析要检索的 collections ──
        if kb_ids:
            # TODO: 从 DB 查 kb → collection_name 映射
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import select, text
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text("SELECT collection_name FROM knowledge_base WHERE id IN :ids AND status='active'"),
                    {"ids": tuple(kb_ids)},
                )
                collection_names = [row[0] for row in result.fetchall()]
        else:
            # 按 channel 查所有活跃 KB
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as session:
                if config.force_public_only:
                    result = await session.execute(
                        text("SELECT collection_name FROM knowledge_base WHERE channel_type=:ch AND status='active'"),
                        {"ch": "cs_agent"},
                    )
                else:
                    result = await session.execute(
                        text("SELECT collection_name FROM knowledge_base WHERE status='active'")
                    )
                collection_names = [row[0] for row in result.fetchall()]

        if not collection_names:
            return self._refuse_response(
                config, conv_id, trace_id, "暂无可用知识库，请联系管理员",
                int((time.time() - start_time) * 1000)
            )

        # ── Step 3: 加载历史记忆 ──
        history_text = memory_service.format_history(conv_id)

        # ── Step 4: 多 collection 并行检索 ──
        raw_docs = vector_store_service.search_multiple_collections(
            collection_names=collection_names,
            query=question,
            k_per_collection=config.retrieval_top_n,
            filter_dict=permission_filter,
        )

        if not raw_docs:
            return self._refuse_response(
                config, conv_id, trace_id, "未找到相关资料",
                int((time.time() - start_time) * 1000),
                collection_names,
            )

        # ── Step 5: 构建检索结果 ──
        retrieval_results = []
        for i, doc in enumerate(raw_docs):
            retrieval_results.append(RetrievalResult(
                chunk_id=doc.metadata.get("chunk_id", f"chunk_{i}"),
                content=doc.page_content,
                score=getattr(doc, "score", 0.0) if hasattr(doc, "score") else 0.0,
                doc_title=doc.metadata.get("doc_title", "未知文档"),
                page_no=doc.metadata.get("page_no", 0),
                doc_id=doc.metadata.get("doc_id", ""),
                security_level=doc.metadata.get("security_level", "公开"),
            ))

        # ── Step 6: Rerank 精排 ──
        doc_texts = [r.content for r in retrieval_results]
        reranked = rerank_service.rerank(question, doc_texts, top_k=config.rerank_top_k)

        # 取精排结果
        top_docs = []
        for idx, score, text in reranked:
            if idx < len(retrieval_results):
                original = retrieval_results[idx]
                original.score = score
                top_docs.append(original)

        if not top_docs:
            return self._refuse_response(
                config, conv_id, trace_id, "检索结果相关性不足",
                int((time.time() - start_time) * 1000),
                collection_names,
            )

        # ── Step 7: 置信度判定 ──
        max_score = max(r.score for r in top_docs)
        confidence = max_score

        # BR-6: 切片 < 2 打 8 折
        if len(top_docs) < 2:
            confidence *= 0.8

        if confidence < config.reject_threshold:
            # 低置信 — 拒答或转人工
            if config.refuse_to_handoff:
                return RAGResponse(
                    answer="很抱歉，我暂时无法回答这个问题，正在为您转接人工客服...",
                    refused=True, handoff=True,
                    trace_id=trace_id, conversation_id=conv_id,
                    latency_ms=int((time.time() - start_time) * 1000),
                    used_collections=collection_names,
                )
            else:
                return RAGResponse(
                    answer="抱歉，当前知识库中没有找到足够的信息来回答这个问题。建议您换个问法或联系管理员补充相关资料。",
                    refused=True,
                    trace_id=trace_id, conversation_id=conv_id,
                    latency_ms=int((time.time() - start_time) * 1000),
                    used_collections=collection_names,
                )

        # ── Step 8: 构建上下文 ──
        context_parts = []
        citations = []
        for i, r in enumerate(top_docs):
            ref_no = i + 1
            context_parts.append(f"[{ref_no}] 来源: {r.doc_title} (页码: {r.page_no})\n{r.content}")
            citations.append({
                "no": ref_no,
                "doc": r.doc_title,
                "page": r.page_no,
                "snippet": r.content[:200],
                "score": round(r.score, 4),
            })
        context_str = "\n\n---\n\n".join(context_parts)

        # ── Step 9: 构建 Prompt ──
        prompt_template = config.system_prompt
        prompt = prompt_template.format(
            context=context_str,
            history=history_text,
            question=question,
        )

        messages = [{"role": "system", "content": prompt}]

        # ── Step 10: LLM 生成 ──
        latency_ms = int((time.time() - start_time) * 1000)

        if stream:
            return self._stream_response(
                messages=messages,
                config=config,
                conv_id=conv_id,
                trace_id=trace_id,
                citations=citations,
                confidence=confidence,
                collection_names=collection_names,
                question=question,
                start_time=start_time,
            )
        else:
            # 非流式
            answer = llm_service.generate_sync(
                messages=messages,
                temperature=config.temperature,
            )

            # ── Step 11: 引用后校验（BR-5：无引用即拒答）──
            has_citation = any(f"[{c['no']}]" in answer for c in citations)
            if not has_citation:
                answer = "抱歉，当前检索到的资料不足以形成可靠回答，请换个问法。"

            # 更新记忆
            memory_service.add_message(conv_id, "user", question)
            memory_service.add_message(conv_id, "assistant", answer)

            latency_ms = int((time.time() - start_time) * 1000)

            return RAGResponse(
                answer=answer,
                citations=citations,
                confidence=round(confidence, 4),
                trace_id=trace_id,
                conversation_id=conv_id,
                latency_ms=latency_ms,
                used_collections=collection_names,
            )

    async def _stream_response(
        self,
        messages: List[dict],
        config: ChannelConfig,
        conv_id: str,
        trace_id: str,
        citations: List[dict],
        confidence: float,
        collection_names: List[str],
        question: str,
        start_time: float,
    ):
        """流式响应生成器"""
        # 返回一个特殊标记，让调用方知道需要用流式处理
        return {
            "_stream": True,
            "messages": messages,
            "temperature": config.temperature,
            "conv_id": conv_id,
            "trace_id": trace_id,
            "citations": citations,
            "confidence": confidence,
            "collection_names": collection_names,
            "question": question,
            "start_time": start_time,
        }

    def _refuse_response(
        self,
        config: ChannelConfig,
        conv_id: str,
        trace_id: str,
        message: str,
        latency_ms: int,
        collections: List[str] = None,
    ) -> RAGResponse:
        """构建拒答响应"""
        if config.refuse_to_handoff:
            return RAGResponse(
                answer="很抱歉，我暂时无法回答这个问题，正在为您转接人工客服...",
                refused=True, handoff=True,
                trace_id=trace_id, conversation_id=conv_id,
                latency_ms=latency_ms,
                used_collections=collections or [],
            )
        return RAGResponse(
            answer=message,
            refused=True,
            trace_id=trace_id, conversation_id=conv_id,
            latency_ms=latency_ms,
            used_collections=collections or [],
        )


# 全局单例
rag_service = RAGService()