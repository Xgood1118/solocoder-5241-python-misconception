from fastapi import APIRouter, Query, Response
from typing import Optional
from datetime import datetime
from models import Student, KnowledgePoint, MistakeRecord, MISTAKE_TYPES
from storage import storage
from collections import defaultdict

router = APIRouter(prefix="/api/export", tags=["export"])


def _get_students_by_class(class_name: Optional[str] = None):
    students = storage.get_all("students", Student)
    if class_name:
        students = [s for s in students if s.class_name == class_name]
    return students


def _get_filtered_mistakes(class_name: Optional[str] = None, exam_name: Optional[str] = None):
    mistakes = storage.get_all("mistakes", MistakeRecord)
    if class_name:
        students = _get_students_by_class(class_name)
        student_ids = {s.id for s in students}
        mistakes = [m for m in mistakes if m.student_id in student_ids]
    if exam_name:
        mistakes = [m for m in mistakes if m.exam_name == exam_name]
    return mistakes


def _generate_html(
    class_name: Optional[str],
    exam_name: Optional[str],
    common_threshold: float,
):
    students = _get_students_by_class(class_name)
    mistakes = _get_filtered_mistakes(class_name, exam_name)
    kps = storage.get_all("knowledge_points", KnowledgePoint)
    kp_map = {kp.id: kp for kp in kps}
    student_map = {s.id: s for s in students}

    total_students = len(students)
    total_mistakes = len(mistakes)

    type_stats = {t: 0 for t in MISTAKE_TYPES}
    for m in mistakes:
        if m.mistake_type in type_stats:
            type_stats[m.mistake_type] += 1

    kp_stats = defaultdict(lambda: {"count": 0, "by_type": defaultdict(int), "students": set()})
    for m in mistakes:
        for kp_id in m.knowledge_point_ids:
            kp_stats[kp_id]["count"] += 1
            kp_stats[kp_id]["by_type"][m.mistake_type] += 1
            kp_stats[kp_id]["students"].add(m.student_id)

    kp_list = []
    for kp_id, data in sorted(kp_stats.items(), key=lambda x: -x[1]["count"]):
        kp = kp_map.get(kp_id)
        kp_name = kp.name if kp else f"未知({kp_id})"
        kp_list.append({
            "name": kp_name,
            "count": data["count"],
            "student_count": len(data["students"]),
            "by_type": dict(data["by_type"]),
        })

    question_groups = defaultdict(list)
    for m in mistakes:
        question_groups[m.question_fingerprint].append(m)

    common_mistakes = []
    for fp, ms in question_groups.items():
        wrong_students = set(m.student_id for m in ms)
        ratio = len(wrong_students) / total_students if total_students > 0 else 0
        if ratio >= common_threshold:
            sample = ms[0]
            m_types = defaultdict(int)
            for m in ms:
                m_types[m.mistake_type] += 1
            kp_names = [kp_map[kp_id].name for kp_id in sample.knowledge_point_ids if kp_id in kp_map]
            common_mistakes.append({
                "question": sample.question_text,
                "wrong_count": len(wrong_students),
                "ratio": round(ratio * 100, 1),
                "by_type": dict(m_types),
                "knowledge_points": kp_names,
            })
    common_mistakes.sort(key=lambda x: -x["wrong_count"])

    student_mistakes = defaultdict(list)
    for m in mistakes:
        student_mistakes[m.student_id].append(m)

    personal_books = []
    for student in students:
        s_mistakes = student_mistakes.get(student.id, [])
        if not s_mistakes:
            continue
        s_kp_stats = defaultdict(lambda: {"count": 0, "by_type": defaultdict(int), "questions": []})
        s_type_stats = defaultdict(int)
        for m in s_mistakes:
            s_type_stats[m.mistake_type] += 1
            for kp_id in m.knowledge_point_ids:
                s_kp_stats[kp_id]["count"] += 1
                s_kp_stats[kp_id]["by_type"][m.mistake_type] += 1
                s_kp_stats[kp_id]["questions"].append({
                    "text": m.question_text,
                    "type": m.mistake_type,
                    "detail": m.mistake_detail,
                    "exam": m.exam_name or "",
                })

        s_kp_list = []
        for kp_id, data in sorted(s_kp_stats.items(), key=lambda x: -x[1]["count"]):
            kp = kp_map.get(kp_id)
            kp_name = kp.name if kp else f"未知({kp_id})"
            s_kp_list.append({
                "name": kp_name,
                "count": data["count"],
                "by_type": dict(data["by_type"]),
                "questions": data["questions"],
            })

        weak_points = [kp for kp in s_kp_list if kp["count"] >= 2]

        personal_books.append({
            "student_id": student.id,
            "student_name": student.name,
            "total": len(s_mistakes),
            "by_type": dict(s_type_stats),
            "by_kp": s_kp_list,
            "weak_points": weak_points,
        })
    personal_books.sort(key=lambda x: -x["total"])

    type_colors = {
        "计算错误": "#3498db",
        "概念不清": "#e74c3c",
        "审题错误": "#f39c12",
        "不会做": "#9b59b6",
    }

    type_bars_html = ""
    for t, count in type_stats.items():
        pct = round(count / total_mistakes * 100, 1) if total_mistakes > 0 else 0
        color = type_colors.get(t, "#999")
        type_bars_html += f"""
        <div class="type-bar">
            <div class="type-label">{t}</div>
            <div class="type-bar-wrap">
                <div class="type-bar-fill" style="width:{pct}%;background:{color}"></div>
            </div>
            <div class="type-count">{count} 题 ({pct}%)</div>
        </div>
        """

    kp_table_html = ""
    for i, kp in enumerate(kp_list[:20], 1):
        type_badges = " ".join(
            f'<span class="badge" style="background:{type_colors.get(t, "#999")}">{t} {c}</span>'
            for t, c in kp["by_type"].items()
        )
        kp_table_html += f"""
        <tr>
            <td>{i}</td>
            <td>{kp['name']}</td>
            <td>{kp['count']}</td>
            <td>{kp['student_count']}</td>
            <td>{type_badges}</td>
        </tr>
        """

    common_html = ""
    for i, cm in enumerate(common_mistakes, 1):
        kp_tags = " ".join(f'<span class="kp-tag">{kp}</span>' for kp in cm["knowledge_points"])
        type_badges = " ".join(
            f'<span class="badge" style="background:{type_colors.get(t, "#999")}">{t} {c}人</span>'
            for t, c in cm["by_type"].items()
        )
        common_html += f"""
        <div class="mistake-card">
            <div class="mistake-header">
                <span class="rank">#{i}</span>
                <span class="wrong-count">{cm['wrong_count']}人错 ({cm['ratio']}%)</span>
            </div>
            <div class="question-text">{cm['question']}</div>
            <div class="mistake-meta">
                <div class="kp-tags">{kp_tags}</div>
                <div class="type-badges">{type_badges}</div>
            </div>
        </div>
        """

    personal_html = ""
    for pb in personal_books:
        weak_section = ""
        if pb["weak_points"]:
            weak_items = "".join(
                f'<li>{wp["name"]} — {wp["count"]}次错题</li>'
                for wp in pb["weak_points"]
            )
            weak_section = f"""
            <div class="weak-section">
                <h4>薄弱知识点</h4>
                <ul>{weak_items}</ul>
            </div>
            """

        kp_detail_html = ""
        for kp in pb["by_kp"]:
            q_html = "".join(
                f'<li><span class="q-type" style="background:{type_colors.get(q["type"], "#999")}">{q["type"]}</span> {q["text"]} <span class="q-detail">{q["detail"]}</span></li>'
                for q in kp["questions"]
            )
            type_badges = " ".join(
                f'<span class="badge small" style="background:{type_colors.get(t, "#999")}">{t} {c}</span>'
                for t, c in kp["by_type"].items()
            )
            kp_detail_html += f"""
            <div class="kp-detail">
                <div class="kp-title">
                    <strong>{kp['name']}</strong>
                    <span class="kp-count">{kp['count']}题</span>
                    {type_badges}
                </div>
                <ul class="question-list">{q_html}</ul>
            </div>
            """

        type_summary = " ".join(
            f'<span class="badge" style="background:{type_colors.get(t, "#999")}">{t} {c}</span>'
            for t, c in pb["by_type"].items()
        )

        personal_html += f"""
        <div class="student-book">
            <div class="student-header">
                <h3>{pb['student_name']} <span class="student-id">({pb['student_id']})</span></h3>
                <div class="student-stats">
                    <span>共 {pb['total']} 道错题</span>
                    {type_summary}
                </div>
            </div>
            {weak_section}
            <div class="kp-breakdown">{kp_detail_html}</div>
        </div>
        """

    class_title = class_name or "全部班级"
    exam_title = exam_name or "全部考试"
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>错题分析报告 - {class_title}</title>
<style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: #f5f7fa; color: #333; padding: 20px; }}
    .container {{ max-width: 1000px; margin: 0 auto; }}
    .header {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
    .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
    .header .subtitle {{ opacity: 0.9; font-size: 14px; }}
    .section {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .section h2 {{ font-size: 18px; margin-bottom: 15px; color: #333; border-left: 4px solid #667eea; padding-left: 10px; }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
    .stat-card {{ background: #f8f9fc; padding: 15px; border-radius: 8px; text-align: center; }}
    .stat-card .num {{ font-size: 28px; font-weight: bold; color: #667eea; }}
    .stat-card .label {{ font-size: 13px; color: #666; margin-top: 5px; }}
    .type-bar {{ display: flex; align-items: center; margin-bottom: 10px; }}
    .type-label {{ width: 80px; font-size: 13px; flex-shrink: 0; }}
    .type-bar-wrap {{ flex: 1; height: 24px; background: #eee; border-radius: 12px; overflow: hidden; margin: 0 10px; }}
    .type-bar-fill {{ height: 100%; border-radius: 12px; transition: width 0.3s; }}
    .type-count {{ width: 100px; font-size: 12px; color: #666; text-align: right; flex-shrink: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; font-size: 13px; }}
    th {{ background: #f8f9fc; font-weight: 600; color: #555; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; color: white; font-size: 11px; margin-right: 4px; }}
    .badge.small {{ font-size: 10px; padding: 1px 6px; }}
    .mistake-card {{ border: 1px solid #eee; border-radius: 8px; padding: 15px; margin-bottom: 12px; }}
    .mistake-header {{ display: flex; justify-content: space-between; margin-bottom: 10px; }}
    .rank {{ background: #e74c3c; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
    .wrong-count {{ color: #e74c3c; font-weight: bold; font-size: 13px; }}
    .question-text {{ background: #f8f9fc; padding: 10px; border-radius: 6px; font-size: 14px; line-height: 1.6; margin-bottom: 10px; white-space: pre-wrap; }}
    .mistake-meta {{ display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }}
    .kp-tags, .type-badges {{ display: flex; flex-wrap: wrap; gap: 4px; }}
    .kp-tag {{ background: #e8f4fd; color: #2980b9; padding: 2px 8px; border-radius: 10px; font-size: 11px; }}
    .student-book {{ border: 1px solid #eee; border-radius: 8px; padding: 15px; margin-bottom: 15px; }}
    .student-header {{ margin-bottom: 12px; }}
    .student-header h3 {{ font-size: 16px; color: #333; margin-bottom: 8px; }}
    .student-id {{ color: #999; font-weight: normal; font-size: 13px; }}
    .student-stats {{ display: flex; gap: 8px; flex-wrap: wrap; font-size: 12px; }}
    .weak-section {{ background: #fff5f5; border-left: 3px solid #e74c3c; padding: 10px 15px; margin-bottom: 12px; border-radius: 0 6px 6px 0; }}
    .weak-section h4 {{ font-size: 13px; color: #c0392b; margin-bottom: 5px; }}
    .weak-section ul {{ list-style: none; padding-left: 0; }}
    .weak-section li {{ font-size: 12px; padding: 2px 0; color: #666; }}
    .kp-detail {{ margin-bottom: 10px; }}
    .kp-title {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 5px; }}
    .kp-count {{ color: #667eea; font-weight: bold; font-size: 13px; }}
    .question-list {{ list-style: none; padding-left: 20px; }}
    .question-list li {{ font-size: 12px; padding: 4px 0; line-height: 1.5; color: #555; }}
    .q-type {{ display: inline-block; padding: 0 6px; border-radius: 3px; color: white; font-size: 10px; margin-right: 6px; }}
    .q-detail {{ color: #999; font-style: italic; }}
    .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
    @media print {{
        body {{ background: white; padding: 0; }}
        .section {{ break-inside: avoid; box-shadow: none; border: 1px solid #eee; }}
    }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>📊 错题分析报告</h1>
        <div class="subtitle">班级：{class_title} | 考试：{exam_title} | 生成时间：{gen_time}</div>
    </div>

    <div class="section">
        <h2>一、班级整体情况</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="num">{total_students}</div><div class="label">学生总数</div></div>
            <div class="stat-card"><div class="num">{total_mistakes}</div><div class="label">错题总数</div></div>
            <div class="stat-card"><div class="num">{len(question_groups)}</div><div class="label">不同题目数</div></div>
            <div class="stat-card"><div class="num">{len(common_mistakes)}</div><div class="label">共性错题</div></div>
        </div>
        <h3 style="font-size:14px;margin:15px 0 10px;">错因分布</h3>
        {type_bars_html}
    </div>

    <div class="section">
        <h2>二、各知识点错题分布</h2>
        <table>
            <thead>
                <tr><th>排名</th><th>知识点</th><th>错题数</th><th>涉及学生</th><th>错因分布</th></tr>
            </thead>
            <tbody>
                {kp_table_html}
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>三、共性错题清单</h2>
        <p style="font-size:12px;color:#666;margin-bottom:10px;">判定标准：班级 {common_threshold*100:.0f}% 以上学生做错</p>
        {common_html if common_html else '<p style="color:#999;">暂无共性错题</p>'}
    </div>

    <div class="section">
        <h2>四、个人错题本</h2>
        {personal_html if personal_html else '<p style="color:#999;">暂无错题数据</p>'}
    </div>

    <div class="footer">
        本报告由错题分析系统自动生成
    </div>
</div>
</body>
</html>"""

    return html


@router.get("/report.html")
def export_report(
    class_name: Optional[str] = None,
    exam_name: Optional[str] = None,
    common_threshold: float = Query(0.5, ge=0.1, le=1.0),
):
    html = _generate_html(class_name, exam_name, common_threshold)
    filename = f"错题分析报告_{class_name or '全部'}_{datetime.now().strftime('%Y%m%d')}.html"
    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Content-Disposition": f"attachment; filename={filename.encode('utf-8').decode('latin-1')}"
        }
    )


@router.get("/report/preview")
def preview_report(
    class_name: Optional[str] = None,
    exam_name: Optional[str] = None,
    common_threshold: float = Query(0.5, ge=0.1, le=1.0),
):
    html = _generate_html(class_name, exam_name, common_threshold)
    return Response(content=html, media_type="text/html")
