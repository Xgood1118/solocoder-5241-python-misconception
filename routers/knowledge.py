from fastapi import APIRouter, HTTPException
from typing import List
import uuid
from models import KnowledgePoint, KnowledgePointCreate
from storage import storage

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("", response_model=List[KnowledgePoint])
def list_knowledge_points():
    return storage.get_all("knowledge_points", KnowledgePoint)


@router.get("/{kp_id}", response_model=KnowledgePoint)
def get_knowledge_point(kp_id: str):
    kp = storage.get_by_id("knowledge_points", KnowledgePoint, kp_id)
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return kp


@router.post("", response_model=KnowledgePoint)
def create_knowledge_point(kp_data: KnowledgePointCreate):
    kp_id = str(uuid.uuid4())[:8]
    kp = KnowledgePoint(id=kp_id, **kp_data.model_dump())
    storage.add("knowledge_points", kp)
    return kp


@router.put("/{kp_id}", response_model=KnowledgePoint)
def update_knowledge_point(kp_id: str, kp_data: KnowledgePointCreate):
    existing = storage.get_by_id("knowledge_points", KnowledgePoint, kp_id)
    if not existing:
        raise HTTPException(status_code=404, detail="知识点不存在")
    storage.update("knowledge_points", kp_id, kp_data.model_dump())
    return storage.get_by_id("knowledge_points", KnowledgePoint, kp_id)


@router.delete("/{kp_id}")
def delete_knowledge_point(kp_id: str):
    success = storage.delete("knowledge_points", kp_id)
    if not success:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return {"message": "删除成功"}
