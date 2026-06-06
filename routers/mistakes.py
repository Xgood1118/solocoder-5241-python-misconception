from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
import uuid
from models import (
    MistakeRecord, MistakeRecordCreate, Student, KnowledgePoint,
    generate_question_fingerprint, MISTAKE_TYPES
)
from storage import storage

router = APIRouter(prefix="/api/mistakes", tags=["mistakes"])


@router.get("", response_model=List[MistakeRecord])
def list_mistakes(
    student_id: Optional[str] = None,
    class_name: Optional[str] = None,
    mistake_type: Optional[str] = None,
    knowledge_point_id: Optional[str] = None,
    exam_name: Optional[str] = None,
):
    mistakes = storage.get_all("mistakes", MistakeRecord)

    if student_id:
        mistakes = [m for m in mistakes if m.student_id == student_id]

    if class_name:
        students = storage.get_all("students", Student)
        student_ids = [s.id for s in students if s.class_name == class_name]
        mistakes = [m for m in mistakes if m.student_id in student_ids]

    if mistake_type:
        mistakes = [m for m in mistakes if m.mistake_type == mistake_type]

    if knowledge_point_id:
        mistakes = [m for m in mistakes if knowledge_point_id in m.knowledge_point_ids]

    if exam_name:
        mistakes = [m for m in mistakes if m.exam_name == exam_name]

    return mistakes


@router.get("/{mistake_id}", response_model=MistakeRecord)
def get_mistake(mistake_id: str):
    mistake = storage.get_by_id("mistakes", MistakeRecord, mistake_id)
    if not mistake:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    return mistake


@router.post("")
def create_mistake(mistake_data: MistakeRecordCreate) -> Dict[str, Any]:
    student = storage.get_by_id("students", Student, mistake_data.student_id)
    if not student:
        raise HTTPException(status_code=400, detail="学生不存在")

    if mistake_data.mistake_type not in MISTAKE_TYPES:
        raise HTTPException(status_code=400, detail=f"错因类型必须是: {', '.join(MISTAKE_TYPES)}")

    fingerprint = generate_question_fingerprint(mistake_data.question_text)

    mistakes = storage.get_all("mistakes", MistakeRecord)
    for m in mistakes:
        if m.student_id == mistake_data.student_id and m.question_fingerprint == fingerprint:
            if (not mistake_data.exam_name and not m.exam_name) or \
               (mistake_data.exam_name and m.exam_name and mistake_data.exam_name == m.exam_name):
                raise HTTPException(
                    status_code=400,
                    detail="该学生此题已录入过（相同考试），请勿重复录入"
                )

    warnings = []
    if len(mistake_data.knowledge_point_ids) == 0:
        warnings.append(
            "该题未关联任何知识点标签，建议补充后再保存，否则后续按知识点维度的统计会遗漏这道题"
        )

    if not mistake_data.exam_name:
        warnings.append(
            "未填写考试名称，后续无法按考试维度筛选统计"
        )

    mistake_id = str(uuid.uuid4())
    mistake = MistakeRecord(
        id=mistake_id,
        question_fingerprint=fingerprint,
        **mistake_data.model_dump()
    )
    storage.add("mistakes", mistake)

    return {
        "record": mistake.model_dump(),
        "warnings": warnings,
    }


@router.put("/{mistake_id}")
def update_mistake(mistake_id: str, mistake_data: MistakeRecordCreate) -> Dict[str, Any]:
    existing = storage.get_by_id("mistakes", MistakeRecord, mistake_id)
    if not existing:
        raise HTTPException(status_code=404, detail="错题记录不存在")

    if mistake_data.mistake_type not in MISTAKE_TYPES:
        raise HTTPException(status_code=400, detail=f"错因类型必须是: {', '.join(MISTAKE_TYPES)}")

    fingerprint = generate_question_fingerprint(mistake_data.question_text)

    update_dict = mistake_data.model_dump()
    update_dict["question_fingerprint"] = fingerprint
    storage.update("mistakes", mistake_id, update_dict)

    updated = storage.get_by_id("mistakes", MistakeRecord, mistake_id)

    warnings = []
    if len(mistake_data.knowledge_point_ids) == 0:
        warnings.append(
            "该题未关联任何知识点标签，建议补充后再保存，否则后续按知识点维度的统计会遗漏这道题"
        )

    if not mistake_data.exam_name:
        warnings.append(
            "未填写考试名称，后续无法按考试维度筛选统计"
        )

    return {
        "record": updated.model_dump(),
        "warnings": warnings,
    }


@router.delete("/{mistake_id}")
def delete_mistake(mistake_id: str):
    success = storage.delete("mistakes", mistake_id)
    if not success:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    return {"message": "删除成功"}


@router.get("/types/list")
def list_mistake_types():
    return {"types": MISTAKE_TYPES}


@router.get("/exams/list")
def list_exams():
    mistakes = storage.get_all("mistakes", MistakeRecord)
    exams = sorted(set(m.exam_name for m in mistakes if m.exam_name))
    return {"exams": exams}


@router.post("/check-duplicate")
def check_duplicate(student_id: str, question_text: str, exam_name: Optional[str] = None):
    fingerprint = generate_question_fingerprint(question_text)
    mistakes = storage.get_all("mistakes", MistakeRecord)
    for m in mistakes:
        if m.student_id == student_id and m.question_fingerprint == fingerprint:
            if (not exam_name and not m.exam_name) or \
               (exam_name and m.exam_name and exam_name == m.exam_name):
                return {"is_duplicate": True, "existing_id": m.id}
    return {"is_duplicate": False}


@router.get("/unlabeled/count")
def count_unlabeled_mistakes():
    mistakes = storage.get_all("mistakes", MistakeRecord)
    unlabeled = [m for m in mistakes if len(m.knowledge_point_ids) == 0]
    return {
        "total": len(mistakes),
        "unlabeled": len(unlabeled),
        "unlabeled_ids": [m.id for m in unlabeled]
    }
