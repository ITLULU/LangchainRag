"""知识库管理 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.deps import get_current_user, CurrentUser, require_role
from app.services.kb_service import kb_service
from app.schemas.kb import KBCreate, KBUpdate, KBOut, KbGrantCreate, KbGrantOut, PaginatedResponse

router = APIRouter(prefix="/api/kb", tags=["知识库管理"])


@router.post("", response_model=KBOut)
async def create_kb(
    data: KBCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """创建知识库"""
    kb = await kb_service.create_kb(db, data, current_user.id)
    return KBOut.model_validate(kb)


@router.get("", response_model=PaginatedResponse)
async def list_kbs(
    channel_type: Optional[str] = Query(None, description="employee_kb 或 cs_agent"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """知识库列表"""
    items, total = await kb_service.list_kbs(
        db, channel_type=channel_type, page=page, page_size=page_size,
    )
    return PaginatedResponse(
        items=[KBOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{kb_id}", response_model=KBOut)
async def get_kb(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取知识库详情"""
    kb = await kb_service.get_kb(db, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return KBOut.model_validate(kb)


@router.put("/{kb_id}", response_model=KBOut)
async def update_kb(
    kb_id: str,
    data: KBUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("platform_admin", "kb_admin")),
):
    """编辑知识库"""
    kb = await kb_service.update_kb(db, kb_id, data)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return KBOut.model_validate(kb)


@router.delete("/{kb_id}")
async def delete_kb(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("platform_admin", "kb_admin")),
):
    """删除知识库"""
    ok = await kb_service.delete_kb(db, kb_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"message": "已删除"}


@router.post("/{kb_id}/permissions", response_model=KbGrantOut)
async def grant_kb_access(
    kb_id: str,
    data: KbGrantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("platform_admin", "kb_admin", "dept_admin")),
):
    """授权知识库访问"""
    kb = await kb_service.get_kb(db, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    grant = await kb_service.grant_access(db, kb_id, data.grantee_type, data.grantee_id, data.can_read)
    return KbGrantOut.model_validate(grant)


@router.get("/{kb_id}/permissions")
async def list_grants(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取知识库授权列表"""
    grants = await kb_service.get_grants(db, kb_id)
    return [KbGrantOut.model_validate(g) for g in grants]


@router.delete("/{kb_id}/permissions/{grant_id}")
async def revoke_grant(
    kb_id: str,
    grant_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("platform_admin", "kb_admin", "dept_admin")),
):
    """撤销授权"""
    ok = await kb_service.remove_grant(db, grant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="授权记录不存在")
    return {"message": "已撤销"}