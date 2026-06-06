import urllib.request
import urllib.parse
import json
import sys

BASE = 'http://127.0.0.1:8080/api'

def post(path, data):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read())

def get(path):
    return json.loads(urllib.request.urlopen(BASE + path).read())

print("=" * 60)
print("测试1：POST 一道不带知识点的错题，检查是否返回 warnings")
print("=" * 60)

try:
    post('/students', {'id': 'test001', 'name': '测试学生', 'class_name': '测试班'})
except Exception:
    pass

result = post('/mistakes', {
    'student_id': 'test001',
    'question_text': '这是一道测试题，没有挂知识点',
    'mistake_type': '计算错误',
    'mistake_detail': '',
    'knowledge_point_ids': [],
    'exam_name': '测试考试'
})

print(f"返回结构包含 record: {'record' in result}")
print(f"返回结构包含 warnings: {'warnings' in result}")
print(f"warnings 数量: {len(result.get('warnings', []))}")
print(f"warnings 内容:")
for w in result.get('warnings', []):
    print(f"  - {w}")

has_kp_warning = any('知识点' in w for w in result.get('warnings', []))
print(f"\n是否包含知识点相关警告: {has_kp_warning}")

if not has_kp_warning:
    print("❌ 测试1失败：未返回知识点缺失的警告")
    sys.exit(1)
else:
    print("✅ 测试1通过")


print()
print("=" * 60)
print("测试2：POST 一道带知识点的错题，检查 warnings 为空")
print("=" * 60)

kp = post('/knowledge', {'name': '测试知识点', 'description': ''})
result2 = post('/mistakes', {
    'student_id': 'test001',
    'question_text': '这道题有知识点标签',
    'mistake_type': '概念不清',
    'mistake_detail': '',
    'knowledge_point_ids': [kp['id']],
    'exam_name': '测试考试'
})

print(f"warnings 数量: {len(result2.get('warnings', []))}")
if len(result2.get('warnings', [])) == 0:
    print("✅ 测试2通过：有知识点的题没有警告")
else:
    print("❌ 测试2失败：有知识点的题也返回了警告")
    sys.exit(1)


print()
print("=" * 60)
print("测试3：知识点统计接口是否包含「未标注知识点」项")
print("=" * 60)

cls = urllib.parse.quote('测试班')
exam = urllib.parse.quote('测试考试')
kp_stats = get(f'/analysis/knowledge-point-stats?class_name={cls}&exam_name={exam}')

print(f"返回结构包含 unlabeled_count: {'unlabeled_count' in kp_stats}")
print(f"unlabeled_count = {kp_stats.get('unlabeled_count')}")
print(f"知识点列表长度: {len(kp_stats['knowledge_points'])}")

has_unlabeled_item = any(kp.get('is_unlabeled') for kp in kp_stats['knowledge_points'])
print(f"列表中包含 is_unlabeled=True 的项: {has_unlabeled_item}")

unlabeled_item = [kp for kp in kp_stats['knowledge_points'] if kp.get('is_unlabeled')]
if unlabeled_item:
    print(f"未标注项名称: {unlabeled_item[0]['knowledge_point_name']}")
    print(f"未标注项错题数: {unlabeled_item[0]['mistake_count']}")

if kp_stats.get('unlabeled_count', 0) >= 1 and has_unlabeled_item:
    print("✅ 测试3通过：知识点统计正确包含未标注项")
else:
    print("❌ 测试3失败")
    sys.exit(1)


print()
print("=" * 60)
print("测试4：学生个人错题本是否包含「未分类」分组")
print("=" * 60)

personal = get('/analysis/student-personal/test001')
print(f"返回结构包含 unlabeled_count: {'unlabeled_count' in personal}")
print(f"unlabeled_count = {personal.get('unlabeled_count')}")
print(f"知识点分组数量: {len(personal['by_knowledge_point'])}")

has_unlabeled_kp = any(kp.get('is_unlabeled') for kp in personal['by_knowledge_point'])
print(f"包含 is_unlabeled=True 的知识点分组: {has_unlabeled_kp}")

unlabeled_kp = [kp for kp in personal['by_knowledge_point'] if kp.get('is_unlabeled')]
if unlabeled_kp:
    print(f"未分类组名称: {unlabeled_kp[0]['knowledge_point_name']}")
    print(f"未分类组错题数: {unlabeled_kp[0]['count']}")

if personal.get('unlabeled_count', 0) >= 1 and has_unlabeled_kp:
    print("✅ 测试4通过：个人错题本正确包含未分类分组")
else:
    print("❌ 测试4失败")
    sys.exit(1)


print()
print("=" * 60)
print("测试5：班级概览是否返回 unlabeled_count")
print("=" * 60)

overview = get(f'/analysis/class-overview?class_name={cls}')
print(f"unlabeled_count = {overview.get('unlabeled_count')}")
if overview.get('unlabeled_count', 0) >= 1:
    print("✅ 测试5通过：班级概览返回了未标注数量")
else:
    print("❌ 测试5失败")
    sys.exit(1)


print()
print("=" * 60)
print("测试6：未标注的错题不会计入 weak_points（薄弱知识点）")
print("=" * 60)

weak = [w for w in personal.get('weak_points', []) if w.get('is_unlabeled')]
print(f"薄弱知识点中包含未分类项: {len(weak) > 0}")
if len(weak) == 0:
    print("✅ 测试6通过：未分类的错题不会被误判为薄弱知识点")
else:
    print("❌ 测试6失败")
    sys.exit(1)


print()
print("🎉 所有测试通过！")
print()
print("修复总结：")
print("  1. POST /api/mistakes 返回 { record, warnings } 结构")
print("  2. PUT /api/mistakes 同样返回 warnings")
print("  3. knowledge-point-stats 增加 unlabeled_count 和「未标注知识点」项")
print("  4. student-personal 增加 unlabeled_count 和「未分类」分组")
print("  5. class-overview 返回 unlabeled_count")
print("  6. 薄弱知识点统计排除未分类项，避免误判")
print("  7. 前端录入页读取后端 warnings 显示黄色警告")
print("  8. 前端分析页概览显示未标注提醒横幅")
print("  9. 前端知识点表格中未标注项标红突出显示")
print("  10. 前端个人错题本显示未标注提醒和未分类分组")
