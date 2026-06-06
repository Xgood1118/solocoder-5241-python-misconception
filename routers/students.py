from fastapi import APIRouter, HTTPException
from typing import List
from models import Student, StudentCreate
from storage import storage

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("", response_model=List[Student])
def list_students(class_name: str = None):
    students = storage.get_all("students", Student)
    if class_name:
        students = [s for s in students if s.class_name == class_name]
    return students


@router.get("/{student_id}", response_model=Student)
def get_student(student_id: str):
    student = storage.get_by_id("students", Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return student


@router.post("", response_model=Student)
def create_student(student_data: StudentCreate):
    existing = storage.get_by_id("students", Student, student_data.id)
    if existing:
        raise HTTPException(status_code=400, detail="学号已存在")
    student = Student(**student_data.model_dump())
    storage.add("students", student)
    return student


@router.put("/{student_id}", response_model=Student)
def update_student(student_id: str, student_data: StudentCreate):
    existing = storage.get_by_id("students", Student, student_id)
    if not existing:
        raise HTTPException(status_code=404, detail="学生不存在")
    if student_data.id != student_id:
        another = storage.get_by_id("students", Student, student_data.id)
        if another:
            raise HTTPException(status_code=400, detail="新学号已存在")
    storage.update("students", student_id, student_data.model_dump())
    return storage.get_by_id("students", Student, student_data.id)


@router.delete("/{student_id}")
def delete_student(student_id: str):
    success = storage.delete("students", student_id)
    if not success:
        raise HTTPException(status_code=404, detail="学生不存在")
    return {"message": "删除成功"}


@router.get("/classes/list")
def list_classes():
    students = storage.get_all("students", Student)
    classes = sorted(set(s.class_name for s in students))
    return {"classes": classes}
