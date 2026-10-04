"""文档管理 API——上传、列表、详情、切分预览、入库任务"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.deps import get_current_user, CurrentUser
from app.services.document_service import document_service
from app.services.kb_service import kb_service
from app.schemas.document import (
    DocumentCreate, DocumentUpdate, DocumentOut,
    DocVersionOut, IngestTaskOut, ChunkPreviewOut,
)
from app.schemas.kb import PaginatedResponse

router = APIRouter(prefix="/api/documents", tags=["文档管理"])


@router.post("", response_model=DocumentOut)
async def create_document(
    data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """创建文档（仅元数据）"""
    doc = await document_service.create_document(db, data, current_user.department)
    return DocumentOut.model_validate(doc)


@router.get("", response_model=PaginatedResponse)
async def list_documents(
    kb_id: Optional[str] = Query(None, description="按知识库过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """文档列表"""
    items, total = await document_service.list_documents(
        db, kb_id=kb_id, page=page, page_size=page_size,
    )
    return PaginatedResponse(
        items=[DocumentOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """文档详情"""
    doc = await document_service.get_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentOut.model_validate(doc)


@router.put("/{doc_id}", response_model=DocumentOut)
async def update_document(
    doc_id: str,
    data: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """编辑文档元数据"""
    doc = await document_service.update_document(db, doc_id, data)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentOut.model_validate(doc)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """删除文档"""
    ok = await document_service.delete_document(db, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "已删除"}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    kb_id: str = Form(...),
    title: str = Form(...),
    security_level: str = Form("公开"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """上传文档并触发入库"""
    # 校验文件大小
    max_size = 50 * 1024 * 1024  # 50MB (BR-2)
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="文件大小超过 50MB 限制")

    # 检查 KB 是否存在并获取 collection_name
    kb = await kb_service.get_kb(db, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 创建文档
    from app.schemas.document import DocumentCreate
    doc_create = DocumentCreate(
        kb_id=kb_id,
        title=title,
        security_level=security_level,
        dept=current_user.department,
    )
    doc = await document_service.create_document(db, doc_create, current_user.department)

    # 将文件内容保存到临时路径并触发入库
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "doc.txt")[1]) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            task = await document_service.upload_and_ingest(
                db, doc.id, f, file.filename or "doc.txt",
                kb.collection_name, kb_id,
            )
    finally:
        os.unlink(tmp_path)

    return {
        "doc_id": doc.id,
        "task_id": task.id,
        "status": task.status,
    }


@router.get("/{doc_id}/versions", response_model=List[DocVersionOut])
async def list_versions(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """文档版本列表"""
    versions = await document_service.get_versions(db, doc_id)
    return [DocVersionOut.model_validate(v) for v in versions]


@router.get("/{doc_id}/tasks")
async def list_ingest_tasks(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取入库任务列表"""
    versions = await document_service.get_versions(db, doc_id)
    all_tasks = []
    for v in versions:
        tasks = await document_service.get_ingest_tasks(db, v.id)
        for t in tasks:
            all_tasks.append(IngestTaskOut.model_validate(t))
    return all_tasks


@router.post("/{doc_id}/preview-split", response_model=ChunkPreviewOut)
async def preview_split(
    doc_id: str,
    chunk_size: int = Form(800),
    chunk_overlap: int = Form(150),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """切分预览"""
    try:
        result = await document_service.preview_chunks(
            db, doc_id, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        )
        return ChunkPreviewOut(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))