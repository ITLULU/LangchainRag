"""问答 API——核心 RAG 问答接口（SSE 流式 + OpenAI 兼容）"""
import json
import time
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.session import get_db
from app.core.deps import get_current_user, CurrentUser, get_optional_user
from app.services.rag_service import rag_service
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from app.schemas.qa import (
    AskRequest, AskResponse, ChatCompletionRequest,
    ConversationOut, MessageOut, FeedbackCreate, QueryLogOut, DashboardStats, Citation,
)
from app.schemas.kb import PaginatedResponse
from app.models.conversation import Conversation, Message
from sqlalchemy import select, func

router = APIRouter(tags=["问答"])


@router.post("/api/ask")
async def ask_question(
    data: AskRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    核心问答接口——支持 SSE 流式和非流式两种模式
    
    流程（对应技术方案 §6.2 QaOrchestrator）：
    通道解析 → 会话记忆 → 权限注入 → 混合检索 → Rerank → 置信判定 → LLM生成 → 引用校验
    """
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    result = await rag_service.ask(
        question=data.question,
        channel=data.channel,
        user_id=current_user.id,
        user_security_level=current_user.security_level,
        user_department=current_user.department,
        conversation_id=data.conversation_id,
        kb_ids=data.kb_ids,
        stream=data.stream,
    )

    if isinstance(result, dict) and result.get("_stream"):
        # 流式响应
        return await _stream_answer(
            result, data.channel, current_user, db,
        )
    else:
        # 非流式响应
        r: "RAGResponse" = result
        # 保存消息到 MySQL
        await _save_message(db, r.conversation_id, "user", data.question)
        await _save_message(db, r.conversation_id, "assistant", r.answer, 
                           citations=json.dumps(r.citations, ensure_ascii=False),
                           confidence=r.confidence, refused=r.refused, handoff=r.handoff)

        return AskResponse(
            answer=r.answer,
            citations=[Citation(**c) for c in r.citations],
            confidence=r.confidence,
            refused=r.refused,
            handoff=r.handoff,
            trace_id=r.trace_id,
            conversation_id=r.conversation_id,
        )


async def _stream_answer(
    stream_data: dict,
    channel: str,
    current_user: CurrentUser,
    db: AsyncSession,
):
    """SSE 流式生成响应"""
    messages = stream_data["messages"]
    temperature = stream_data["temperature"]
    conv_id = stream_data["conv_id"]
    trace_id = stream_data["trace_id"]
    citations_data = stream_data["citations"]
    confidence = stream_data["confidence"]
    collection_names = stream_data["collection_names"]
    question = stream_data["question"]

    # 保存用户消息
    await _save_message(db, conv_id, "user", question)

    async def event_generator():
        full_answer = ""
        try:
            async for chunk in llm_service.generate_stream(
                messages=messages,
                temperature=temperature,
            ):
                full_answer += chunk
                yield {
                    "event": "chunk",
                    "data": json.dumps({"content": chunk}, ensure_ascii=False),
                }

            # 引用后校验
            has_citation = any(f"[{c['no']}]" in full_answer for c in citations_data)
            if not has_citation and not stream_data.get("refused"):
                full_answer = "抱歉，当前检索到的资料不足以形成可靠回答，请换个问法。"

            # 发送最终结果
            yield {
                "event": "done",
                "data": json.dumps({
                    "answer": full_answer,
                    "citations": citations_data,
                    "confidence": round(confidence, 4),
                    "refused": False,
                    "handoff": False,
                    "trace_id": trace_id,
                    "conversation_id": conv_id,
                }, ensure_ascii=False),
            }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}, ensure_ascii=False),
            }

    # 保存 assistant 消息
    memory_service.add_message(conv_id, "assistant", "")  # 先占位

    return EventSourceResponse(event_generator())


async def _save_message(
    db: AsyncSession,
    conv_id: str,
    role: str,
    content: str,
    citations: Optional[str] = None,
    confidence: Optional[float] = None,
    refused: bool = False,
    handoff: bool = False,
):
    """保存消息到数据库（异步）"""
    try:
        # 确保会话存在
        from sqlalchemy import text
        result = await db.execute(
            text("SELECT id FROM conversation WHERE id=:cid"),
            {"cid": conv_id},
        )
        if not result.fetchone():
            # 创建会话
            conv = Conversation(id=conv_id, channel="employee_kb", user_id="system")
            db.add(conv)

        msg = Message(
            conv_id=conv_id,
            role=role,
            content_masked=content,
            citations=citations,
            confidence=confidence,
            refused=refused,
            handoff=handoff,
        )
        db.add(msg)
        await db.flush()
    except Exception:
        pass  # 不阻断主流程


@router.post("/v1/chat/completions")
async def chat_completions(
    data: ChatCompletionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """OpenAI 兼容问答接口"""
    # 提取最后一条用户消息作为 question
    user_messages = [m for m in data.messages if m.get("role") == "user"]
    question = user_messages[-1]["content"] if user_messages else ""

    ask_data = AskRequest(
        channel=data.channel,
        question=question,
        conversation_id=data.conversation_id,
        kb_ids=data.kb_ids,
        stream=data.stream,
    )
    return await ask_question(ask_data, request, db, current_user)


# ─── 会话管理 ───

@router.get("/api/conversations", response_model=List[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取当前用户的会话列表"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()

    out = []
    for c in convs:
        count_result = await db.execute(
            select(func.count(Message.id)).where(Message.conv_id == c.id)
        )
        msg_count = count_result.scalar() or 0
        out.append(ConversationOut(
            id=c.id, channel=c.channel, title=c.title,
            created_at=str(c.created_at), message_count=msg_count,
        ))
    return out


@router.get("/api/conversations/{conv_id}/messages", response_model=List[MessageOut])
async def get_messages(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取会话历史消息"""
    result = await db.execute(
        select(Message)
        .where(Message.conv_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    msgs = result.scalars().all()
    return [MessageOut.model_validate(m) for m in msgs]


# ─── 反馈 ───

@router.post("/api/feedback")
async def submit_feedback(
    data: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """提交问答反馈（点赞/点踩）"""
    from app.models.conversation import Feedback
    fb = Feedback(
        query_log_id=data.query_log_id,
        rating=data.rating,
        reason=data.reason,
    )
    db.add(fb)
    await db.flush()
    return {"message": "反馈已提交"}


# ─── 运营看板 ───

@router.get("/api/dashboard/knowledge-ops", response_model=DashboardStats)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """知识运营看板数据"""
    from app.models.kb import KnowledgeBase
    from app.models.document import Document
    from app.models.conversation import QueryLog

    kb_count = (await db.execute(select(func.count(KnowledgeBase.id)))).scalar() or 0
    doc_count = (await db.execute(select(func.count(Document.id)))).scalar() or 0

    # 问答统计
    total_queries = (await db.execute(select(func.count(QueryLog.id)))).scalar() or 0
    avg_conf = (await db.execute(select(func.avg(QueryLog.confidence)))).scalar() or 0.0
    refused = (await db.execute(
        select(func.count(QueryLog.id)).where(QueryLog.refused == True)
    )).scalar() or 0
    reject_rate = (refused / total_queries * 100) if total_queries > 0 else 0.0

    return DashboardStats(
        total_kbs=kb_count,
        total_docs=doc_count,
        total_queries=total_queries,
        avg_confidence=round(float(avg_conf), 4),
        reject_rate=round(reject_rate, 1),
        self_service_rate=round(100 - reject_rate, 1),
        daily_queries=[],
    )