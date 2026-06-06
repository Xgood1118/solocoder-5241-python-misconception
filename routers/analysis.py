from fastapi import APIRouter, Query
from typing import List, Optional, Dict, Any
from collections import defaultdict
from models import MistakeRecord, Student, KnowledgePoint, MISTAKE_TYPES
from storage import storage

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _get_students_by_class(class_name: Optional[str] = None) -> List[Student]:
    students = storage.get_all("students", Student)
    if class_name:
        students = [s for s in students if s.class_name == class_name]
    return students


def _get_filtered_mistakes(
    class_name: Optional[str] = None,
    exam_name: Optional[str] = None,
    knowledge_point_id: Optional[str] = None,
) -> List[MistakeRecord]:
    mistakes = storage.get_all("mistakes", MistakeRecord)

    if class_name:
        students = _get_students_by_class(class_name)
        student_ids = {s.id for s in students}
        mistakes = [m for m in mistakes if m.student_id in student_ids]

    if exam_name:
        mistakes = [m for m in mistakes if m.exam_name == exam_name]

    if knowledge_point_id:
        mistakes = [m for m in mistakes if knowledge_point_id in m.knowledge_point_ids]

    return mistakes


@router.get("/mistake-type-stats")
def mistake_type_stats(
    class_name: Optional[str] = None,
    exam_name: Optional[str] = None,
    knowledge_point_id: Optional[str] = None,
):
    mistakes = _get_filtered_mistakes(class_name, exam_name, knowledge_point_id)

    stats = {t: {"count": 0, "percentage": 0.0} for t in MISTAKE_TYPES}
    total = len(mistakes)

    for m in mistakes:
        if m.mistake_type in stats:
            stats[m.mistake_type]["count"] += 1

    for t in stats:
        if total > 0:
            stats[t]["percentage"] = round(stats[t]["count"] / total * 100, 1)

    return {
        "total": total,
        "by_type": stats,
    }


@router.get("/knowledge-point-stats")
def knowledge_point_stats(
    class_name: Optional[str] = None,
    exam_name: Optional[str] = None,
):
    mistakes = _get_filtered_mistakes(class_name, exam_name)
    kps = storage.get_all("knowledge_points", KnowledgePoint)
    kp_map = {kp.id: kp for kp in kps}

    kp_mistake_count = defaultdict(int)
    kp_mistake_types = defaultdict(lambda: defaultdict(int))
    kp_students = defaultdict(set)

    for m in mistakes:
        for kp_id in m.knowledge_point_ids:
            kp_mistake_count[kp_id] += 1
            kp_mistake_types[kp_id][m.mistake_type] += 1
            kp_students[kp_id].add(m.student_id)

    result = []
    for kp_id, count in sorted(kp_mistake_count.items(), key=lambda x: -x[1]):
        kp = kp_map.get(kp_id)
        if not kp:
            continue
        result.append({
            "knowledge_point_id": kp_id,
            "knowledge_point_name": kp.name,
            "mistake_count": count,
            "student_count": len(kp_students[kp_id]),
            "by_type": dict(kp_mistake_types[kp_id]),
        })

    return {"knowledge_points": result}


@router.get("/common-mistakes")
def common_mistakes(
    class_name: str = None,
    exam_name: Optional[str] = None,
    threshold: float = Query(0.5, ge=0.1, le=1.0, description="共性错题判定阈值（占班级人数比例）"),
):
    students = _get_students_by_class(class_name)
    total_students = len(students)
    if total_students == 0:
        return {"total_students": 0, "common_mistakes": []}

    student_ids = {s.id for s in students}
    mistakes = _get_filtered_mistakes(class_name, exam_name)

    question_groups = defaultdict(list)
    for m in mistakes:
        if m.student_id in student_ids:
            question_groups[m.question_fingerprint].append(m)

    common = []
    for fingerprint, ms in question_groups.items():
        wrong_students = set(m.student_id for m in ms)
        wrong_count = len(wrong_students)
        ratio = wrong_count / total_students

        if ratio >= threshold:
            sample = ms[0]
            mistake_types = defaultdict(int)
            mistake_details = defaultdict(list)
            kp_ids = set()
            for m in ms:
                mistake_types[m.mistake_type] += 1
                if m.mistake_detail:
                    mistake_details[m.mistake_detail].append(m.student_id)
                kp_ids.update(m.knowledge_point_ids)

            kps = storage.get_all("knowledge_points", KnowledgePoint)
            kp_names = [kp.name for kp in kps if kp.id in kp_ids]

            common.append({
                "question_fingerprint": fingerprint,
                "question_text": sample.question_text,
                "wrong_student_count": wrong_count,
                "wrong_ratio": round(ratio * 100, 1),
                "by_type": dict(mistake_types),
                "details": {k: len(v) for k, v in mistake_details.items()},
                "knowledge_points": kp_names,
                "wrong_students": list(wrong_students),
            })

    common.sort(key=lambda x: -x["wrong_student_count"])
    return {
        "total_students": total_students,
        "threshold": threshold,
        "common_mistakes": common,
    }


@router.get("/student-personal/{student_id}")
def student_personal_mistakes(student_id: str):
    student = storage.get_by_id("students", Student, student_id)
    if not student:
        return {"error": "学生不存在"}

    mistakes = [m for m in storage.get_all("mistakes", MistakeRecord) if m.student_id == student_id]

    kp_stats = defaultdict(lambda: {"count": 0, "by_type": defaultdict(int), "mistakes": []})
    type_stats = defaultdict(int)

    for m in mistakes:
        type_stats[m.mistake_type] += 1
        for kp_id in m.knowledge_point_ids:
            kp_stats[kp_id]["count"] += 1
            kp_stats[kp_id]["by_type"][m.mistake_type] += 1
            kp_stats[kp_id]["mistakes"].append({
                "id": m.id,
                "question_text": m.question_text,
                "mistake_type": m.mistake_type,
                "mistake_detail": m.mistake_detail,
                "exam_name": m.exam_name,
                "created_at": m.created_at,
            })

    kps = storage.get_all("knowledge_points", KnowledgePoint)
    kp_map = {kp.id: kp for kp in kps}

    kp_result = []
    for kp_id, data in kp_stats.items():
        kp = kp_map.get(kp_id)
        kp_name = kp.name if kp else f"未知({kp_id})"
        data["knowledge_point_id"] = kp_id
        data["knowledge_point_name"] = kp_name
        data["by_type"] = dict(data["by_type"])
        kp_result.append(data)

    kp_result.sort(key=lambda x: -x["count"])

    weak_points = [kp for kp in kp_result if kp["count"] >= 2]

    return {
        "student": student,
        "total_mistakes": len(mistakes),
        "by_type": dict(type_stats),
        "by_knowledge_point": kp_result,
        "weak_points": weak_points,
    }


@router.get("/personal-weak-points")
def personal_weak_points(
    class_name: Optional[str] = None,
    min_mistakes: int = Query(2, ge=2, description="判定为薄弱点的最少错题数"),
):
    students = _get_students_by_class(class_name)
    mistakes = _get_filtered_mistakes(class_name)

    student_kp_count = defaultdict(lambda: defaultdict(int))
    for m in mistakes:
        for kp_id in m.knowledge_point_ids:
            student_kp_count[m.student_id][kp_id] += 1

    kps = storage.get_all("knowledge_points", KnowledgePoint)
    kp_map = {kp.id: kp for kp in kps}

    result = []
    for student in students:
        kp_counts = student_kp_count.get(student.id, {})
        weak = []
        for kp_id, count in kp_counts.items():
            if count >= min_mistakes:
                kp = kp_map.get(kp_id)
                kp_name = kp.name if kp else f"未知({kp_id})"
                weak.append({
                    "knowledge_point_id": kp_id,
                    "knowledge_point_name": kp_name,
                    "mistake_count": count,
                })
        if weak:
            weak.sort(key=lambda x: -x["mistake_count"])
            result.append({
                "student_id": student.id,
                "student_name": student.name,
                "class_name": student.class_name,
                "weak_points": weak,
            })

    result.sort(key=lambda x: -len(x["weak_points"]))
    return {"students": result}


@router.get("/high-frequency-mistakes")
def high_frequency_mistakes(
    min_students: int = Query(3, ge=2, description="至少被多少个学生做错"),
    min_exams: int = Query(2, ge=2, description="至少出现在多少次考试中"),
):
    mistakes = storage.get_all("mistakes", MistakeRecord)

    question_data = defaultdict(lambda: {
        "students": set(),
        "exams": set(),
        "question_text": "",
        "mistake_types": defaultdict(int),
        "kp_ids": set(),
        "total_count": 0,
    })

    for m in mistakes:
        fp = m.question_fingerprint
        data = question_data[fp]
        data["students"].add(m.student_id)
        if m.exam_name:
            data["exams"].add(m.exam_name)
        if not data["question_text"]:
            data["question_text"] = m.question_text
        data["mistake_types"][m.mistake_type] += 1
        data["kp_ids"].update(m.knowledge_point_ids)
        data["total_count"] += 1

    kps = storage.get_all("knowledge_points", KnowledgePoint)
    kp_map = {kp.id: kp for kp in kps}

    high_freq = []
    for fp, data in question_data.items():
        student_count = len(data["students"])
        exam_count = len(data["exams"])

        if student_count >= min_students and exam_count >= min_exams:
            kp_names = [kp_map[kp_id].name for kp_id in data["kp_ids"] if kp_id in kp_map]
            high_freq.append({
                "question_fingerprint": fp,
                "question_text": data["question_text"],
                "student_count": student_count,
                "exam_count": exam_count,
                "total_mistake_count": data["total_count"],
                "exams": list(data["exams"]),
                "by_type": dict(data["mistake_types"]),
                "knowledge_points": kp_names,
            })

    high_freq.sort(key=lambda x: (-x["student_count"], -x["exam_count"]))
    return {"high_frequency_mistakes": high_freq}


@router.get("/class-overview")
def class_overview(
    class_name: Optional[str] = None,
    exam_name: Optional[str] = None,
    common_threshold: float = Query(0.5, ge=0.1, le=1.0),
):
    students = _get_students_by_class(class_name)
    mistakes = _get_filtered_mistakes(class_name, exam_name)

    type_stats = {t: 0 for t in MISTAKE_TYPES}
    for m in mistakes:
        if m.mistake_type in type_stats:
            type_stats[m.mistake_type] += 1

    kp_count = defaultdict(int)
    for m in mistakes:
        for kp_id in m.knowledge_point_ids:
            kp_count[kp_id] += 1

    kps = storage.get_all("knowledge_points", KnowledgePoint)
    kp_map = {kp.id: kp for kp in kps}
    top_kps = sorted(kp_count.items(), key=lambda x: -x[1])[:5]
    top_kp_list = [
        {"name": kp_map[kp_id].name if kp_id in kp_map else kp_id, "count": count}
        for kp_id, count in top_kps
    ]

    student_mistake_count = defaultdict(int)
    for m in mistakes:
        student_mistake_count[m.student_id] += 1

    student_ids = {s.id for s in students}
    question_groups = defaultdict(list)
    for m in mistakes:
        if m.student_id in student_ids:
            question_groups[m.question_fingerprint].append(m)

    common_count = 0
    for fp, ms in question_groups.items():
        wrong_students = set(m.student_id for m in ms)
        if len(students) > 0 and len(wrong_students) / len(students) >= common_threshold:
            common_count += 1

    unlabeled = sum(1 for m in mistakes if len(m.knowledge_point_ids) == 0)

    return {
        "class_name": class_name or "全部",
        "exam_name": exam_name or "全部考试",
        "total_students": len(students),
        "total_mistakes": len(mistakes),
        "unique_questions": len(question_groups),
        "common_mistake_count": common_count,
        "unlabeled_count": unlabeled,
        "mistake_types": type_stats,
        "top_knowledge_points": top_kp_list,
        "student_mistake_distribution": {
            s.id: student_mistake_count.get(s.id, 0) for s in students
        },
    }
