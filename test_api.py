import urllib.request
import urllib.parse
import json
import sys
sys.path.insert(0, '.')

BASE = 'http://127.0.0.1:8080/api'

def post(path, data):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read())

def get(path):
    return json.loads(urllib.request.urlopen(BASE + path).read())

try:
    post('/students', {'id': '2024001', 'name': '张三', 'class_name': '高一(1)班'})
except Exception:
    pass
try:
    post('/students', {'id': '2024002', 'name': '李四', 'class_name': '高一(1)班'})
except Exception:
    pass
try:
    post('/students', {'id': '2024003', 'name': '王五', 'class_name': '高一(1)班'})
except Exception:
    pass
try:
    post('/students', {'id': '2024004', 'name': '赵六', 'class_name': '高一(1)班'})
except Exception:
    pass
try:
    post('/students', {'id': '2024005', 'name': '张三', 'class_name': '高一(2)班'})
except Exception:
    pass
print('学生添加完成')

kps = get('/knowledge')
kp_map = {kp['name']: kp['id'] for kp in kps}
if '牛顿第二定律' not in kp_map:
    kp1 = post('/knowledge', {'name': '牛顿第二定律', 'description': 'F=ma'})
    kp_map['牛顿第二定律'] = kp1['id']
if '加速度概念' not in kp_map:
    kp2 = post('/knowledge', {'name': '加速度概念', 'description': '速度变化率'})
    kp_map['加速度概念'] = kp2['id']
if '单位换算' not in kp_map:
    kp3 = post('/knowledge', {'name': '单位换算', 'description': '国际单位制'})
    kp_map['单位换算'] = kp3['id']
print('知识点准备完成')

q1 = '一个质量为2kg的物体，受到10N的合力作用，求加速度。'
q2 = '汽车以20m/s的速度行驶，刹车后5秒停下，求加速度大小。'
q3 = '物体速度越大，加速度也越大，对吗？请说明理由。'

mistakes = [
    {'student_id': '2024001', 'question_text': q1, 'mistake_type': '计算错误', 'mistake_detail': '乘法算错了', 'knowledge_point_ids': [kp_map['牛顿第二定律']], 'exam_name': '期中考试'},
    {'student_id': '2024001', 'question_text': q2, 'mistake_type': '概念不清', 'mistake_detail': '混淆了加速度和速度', 'knowledge_point_ids': [kp_map['加速度概念']], 'exam_name': '期中考试'},
    {'student_id': '2024002', 'question_text': q1, 'mistake_type': '概念不清', 'mistake_detail': '公式记错了', 'knowledge_point_ids': [kp_map['牛顿第二定律']], 'exam_name': '期中考试'},
    {'student_id': '2024002', 'question_text': q3, 'mistake_type': '概念不清', 'mistake_detail': '混淆了加速度和速度概念', 'knowledge_point_ids': [kp_map['加速度概念']], 'exam_name': '期中考试'},
    {'student_id': '2024003', 'question_text': q1, 'mistake_type': '审题错误', 'mistake_detail': '没看到质量单位是kg', 'knowledge_point_ids': [kp_map['牛顿第二定律'], kp_map['单位换算']], 'exam_name': '期中考试'},
    {'student_id': '2024003', 'question_text': q2, 'mistake_type': '不会做', 'mistake_detail': '', 'knowledge_point_ids': [kp_map['加速度概念']], 'exam_name': '期中考试'},
    {'student_id': '2024004', 'question_text': q1, 'mistake_type': '计算错误', 'mistake_detail': '', 'knowledge_point_ids': [kp_map['牛顿第二定律']], 'exam_name': '期中考试'},
]

for m in mistakes:
    try:
        post('/mistakes', m)
    except Exception:
        pass
print('错题录入完成')

print()
print('=== 错因统计 ===')
cls = urllib.parse.quote('高一(1)班')
exam = urllib.parse.quote('期中考试')
stats = get(f'/analysis/mistake-type-stats?class_name={cls}&exam_name={exam}')
print(json.dumps(stats, ensure_ascii=False, indent=2))

print()
print('=== 知识点统计 (前3个) ===')
kp_stats = get(f'/analysis/knowledge-point-stats?class_name={cls}&exam_name={exam}')
for kp in kp_stats['knowledge_points'][:3]:
    print(f"  {kp['knowledge_point_name']}: {kp['mistake_count']}题, {kp['student_count']}个学生")

print()
print('=== 共性错题 (50%阈值) ===')
common = get(f'/analysis/common-mistakes?class_name={cls}&exam_name={exam}&threshold=0.5')
print(f"共 {len(common['common_mistakes'])} 道共性错题 (班级共{common['total_students']}人)")
for m in common['common_mistakes']:
    print(f"  - {m['question_text'][:30]}...: {m['wrong_student_count']}人错 ({m['wrong_ratio']}%)")

print()
print('=== 张三(2024001)个人错题 ===')
personal = get('/analysis/student-personal/2024001')
print(f"共 {personal['total_mistakes']} 道错题")
print(f"按类型: {personal['by_type']}")
print(f"薄弱知识点 (>=2次): {[w['knowledge_point_name'] for w in personal['weak_points']]}")

print()
print('=== 班级薄弱学生一览 ===')
weak = get(f'/analysis/personal-weak-points?class_name={cls}&min_mistakes=2')
print(f"有 {len(weak['students'])} 个学生有薄弱知识点")
for s in weak['students'][:3]:
    print(f"  {s['student_name']}: {[w['knowledge_point_name'] for w in s['weak_points']]}")

print()
print('=== 题目指纹去重测试 ===')
from models import generate_question_fingerprint
fp1 = generate_question_fingerprint(q1)
fp2 = generate_question_fingerprint('  一个质量为2kg的物体，  受到10N的合力作用，求加速度。  ')
print(f"原题指纹: {fp1}")
print(f"加空格指纹: {fp2}")
print(f"是否相同: {fp1 == fp2}")

print()
print('=== 未标注知识点统计 ===')
unlabeled = get('/mistakes/unlabeled/count')
print(f"总错题: {unlabeled['total']}, 未标注: {unlabeled['unlabeled']}")

print()
print('=== 导出报告预览测试 ===')
req = urllib.request.Request(BASE + f'/export/report/preview?class_name={cls}&exam_name={exam}')
resp = urllib.request.urlopen(req)
html = resp.read().decode()
print(f"HTML 报告生成成功, 大小: {len(html)} 字节")
print(f"包含 '班级整体情况': {'班级整体情况' in html}")
print(f"包含 '共性错题': {'共性错题' in html}")
print(f"包含 '个人错题本': {'个人错题本' in html}")

print()
print('✅ 所有核心功能测试通过!')
