from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import hashlib
import re


MISTAKE_TYPES = ["计算错误", "概念不清", "审题错误", "不会做"]


def generate_question_fingerprint(question_text: str) -> str:
    cleaned = re.sub(r'\s+', '', question_text)
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', cleaned)
    return hashlib.md5(cleaned.encode('utf-8')).hexdigest()


class Student(BaseModel):
    id: str
    name: str
    class_name: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class KnowledgePoint(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MistakeRecord(BaseModel):
    id: str
    student_id: str
    question_text: str
    question_fingerprint: str
    mistake_type: str
    mistake_detail: str
    knowledge_point_ids: List[str] = []
    exam_name: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MistakeRecordCreate(BaseModel):
    student_id: str
    question_text: str
    mistake_type: str
    mistake_detail: str = ""
    knowledge_point_ids: List[str] = []
    exam_name: Optional[str] = None


class StudentCreate(BaseModel):
    id: str
    name: str
    class_name: str


class KnowledgePointCreate(BaseModel):
    name: str
    description: Optional[str] = None
