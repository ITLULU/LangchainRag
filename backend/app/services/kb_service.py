"""知识库 CRUD 服务"""
import uuid
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb import KnowledgeBase, KbGrant, ChannelType, Visibility
from app.schemas.kb import KBCreate, KBUpdate


class KBService:

    @staticmethod
    async def create_kb(db: AsyncSession, kb_data: KBCreate, user_id: str) -> KnowledgeBase:
        """创建知识库，生成唯一 collection_name"""
        collection_name = f"askkb_{kb_data.channel_type.value}_{uuid.uuid4().hex[:12]}"

        kb = KnowledgeBase(
            name=kb_data.name,
            description=kb_data.description,
            channel_type=kb_data.channel_type,
            collection_name=collection_name,
            owner_dept=kb_data.owner_dept,
            visibility=kb_data.visibility,
            chunk_size=kb_data.chunk_size,
            chunk_overlap=kb_data.chunk_overlap,
            split_strategy=kb_data.split_strategy,
            table_strategy=kb_data.table_strategy,
            reject_threshold=kb_data.reject_threshold,
            top_k_override=kb_data.top_k_override,
            temperature=kb_data.temperature,
            prompt_template=kb_data.prompt_template,
            created_by=user_id,
        )
        db.add(kb)
        await db.flush()
        await db.refresh(kb)
        return kb

    @staticmethod
    async def get_kb(db: AsyncSession, kb_id: str) -> Optional[KnowledgeBase]:
        result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_kbs(
        db: AsyncSession,
        channel_type: Optional[str] = None,
        status: str = "active",
        page: int = 1,
        page_size: int = 20,
        filters: Optional[dict] = None,
    ) -> tuple[List[KnowledgeBase], int]:
        query = select(KnowledgeBase)
        count_query = select(func.count(KnowledgeBase.id))

        if channel_type:
            query = query.where(KnowledgeBase.channel_type == channel_type)
            count_query = count_query.where(KnowledgeBase.channel_type == channel_type)

        if status:
            query = query.where(KnowledgeBase.status == status)
            count_query = count_query.where(KnowledgeBase.status == status)

        if filters:
            if "id_in" in filters:
                query = query.where(KnowledgeBase.id.in_(filters["id_in"]))
                count_query = count_query.where(KnowledgeBase.id.in_(filters["id_in"]))
            if "visibility" in filters:
                query = query.where(KnowledgeBase.visibility == filters["visibility"])
                count_query = count_query.where(KnowledgeBase.visibility == filters["visibility"])
            if "channel_type" in filters and not channel_type:
                query = query.where(KnowledgeBase.channel_type == filters["channel_type"])
                count_query = count_query.where(KnowledgeBase.channel_type == filters["channel_type"])

        # 总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页
        offset = (page - 1) * page_size
        query = query.order_by(KnowledgeBase.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    @staticmethod
    async def update_kb(db: AsyncSession, kb_id: str, data: KBUpdate) -> Optional[KnowledgeBase]:
        kb = await KBService.get_kb(db, kb_id)
        if not kb:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(kb, field, value)

        await db.flush()
        await db.refresh(kb)
        return kb

    @staticmethod
    async def delete_kb(db: AsyncSession, kb_id: str) -> bool:
        kb = await KBService.get_kb(db, kb_id)
        if not kb:
            return False
        await db.delete(kb)
        await db.flush()
        return True

    @staticmethod
    async def grant_access(db: AsyncSession, kb_id: str, grantee_type: str, grantee_id: str, can_read: bool = True) -> KbGrant:
        grant = KbGrant(
            kb_id=kb_id,
            grantee_type=grantee_type,
            grantee_id=grantee_id,
            can_read=can_read,
        )
        db.add(grant)
        await db.flush()
        await db.refresh(grant)
        return grant

    @staticmethod
    async def get_grants(db: AsyncSession, kb_id: str) -> List[KbGrant]:
        result = await db.execute(select(KbGrant).where(KbGrant.kb_id == kb_id))
        return list(result.scalars().all())

    @staticmethod
    async def remove_grant(db: AsyncSession, grant_id: str) -> bool:
        result = await db.execute(select(KbGrant).where(KbGrant.id == grant_id))
        grant = result.scalar_one_or_none()
        if not grant:
            return False
        await db.delete(grant)
        await db.flush()
        return True


# 单例
kb_service = KBService()