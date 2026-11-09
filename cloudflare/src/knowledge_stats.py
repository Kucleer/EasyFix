"""知识点统计的共享聚合服务，供分析与学习报告复用同一口径。

一级按主考点归属计算占比；题数与复习覆盖按任一级关联去重；
“模块练习正确率”来自 practice_set_question 的最终批改状态，不使用题目累计计数器。
题数类指标按题目收录时间过滤，正确率按练习批改时间过滤，两者不互相叠加。
"""

from datetime import datetime, timedelta

from fastapi import HTTPException

COUNTING_MODE = 'level1_primary_share+module_practice_accuracy'


def now():
    """返回与历史数据一致的北京时间。"""
    return datetime.utcnow() + timedelta(hours=8)


async def taxonomy_version(db):
    """读取目录版本号。"""
    row = await db.first("SELECT value FROM runtime_config WHERE name='taxonomy_version' AND deleted=0")
    return str(row['value']) if row else '0'


def scoped_filters(subject_id, grade):
    """构造题目学科与年级筛选，供题数和作答两条 SQL 共用。"""
    filters, values = [], []
    if subject_id is not None:
        filters.append('q.subject_id=?')
        values.append(subject_id)
    if grade is not None:
        filters.append('q.grade=?')
        values.append(grade)
    return filters, values


def recency_filter(days, column):
    """构造时间窗口条件，调用方自行决定使用收录时间还是批改时间。"""
    if not days:
        return [], []
    return [column + '>=?'], [(now() - timedelta(days=days)).isoformat(' ')]


async def module_stats(db, subject_id=None, grade=None, days=None, level=1, parent_id=None,
                       practice_days=None):
    """按一级或二级聚合题数、占比、复习覆盖与模块练习正确率。

    目录节点即使在当前筛选下没有题目也会返回（题数 0、正确率 null），
    保证删除或时间窗口变化后不会静默丢失模块。
    """
    scope, scope_values = scoped_filters(subject_id, grade)
    question_where = ['q.deleted=0', *scope, *recency_filter(days, 'q.created_at')[0]]
    question_values = [*scope_values, *recency_filter(days, 'q.created_at')[1]]
    practice_where = ['pq.deleted=0', 'pq.is_correct IS NOT NULL', *scope,
                      *recency_filter(practice_days, 'p.last_reviewed_at')[0]]
    practice_values = [*scope_values, *recency_filter(practice_days, 'p.last_reviewed_at')[1]]
    node_filters, node_values = ['k.deleted=0', 'k.level=?'], [int(level)]
    if subject_id is not None:
        node_filters.append('k.subject_id=?')
        node_values.append(subject_id)
    if level == 2 and parent_id is not None:
        node_filters.append('k.parent_id=?')
        node_values.append(parent_id)
    directory = await db.all(
        'SELECT k.id,k.name,k.level,k.parent_id,k.subject_id,k.sort_order,s.name AS subject_name,'
        '(SELECT p.name FROM knowledge_point p WHERE p.id=k.parent_id AND p.deleted=0) AS parent_name '
        'FROM knowledge_point k LEFT JOIN subject s ON s.id=k.subject_id AND s.deleted=0 '
        'WHERE ' + ' AND '.join(node_filters) + ' ORDER BY k.sort_order,k.id', node_values)
    if level == 1:
        node_select = ('m.id AS id,m.name AS name,1 AS level,NULL AS parent_id,NULL AS parent_name,'
                       'm.subject_id AS subject_id,s.name AS subject_name')
        node_group = 'm.id'
        node_where, extra_values = [], []
    else:
        node_select = ('k.id AS id,k.name AS name,2 AS level,k.parent_id AS parent_id,'
                       'm.name AS parent_name,k.subject_id AS subject_id,s.name AS subject_name')
        node_group = 'k.id'
        node_where = ['k.parent_id=?'] if parent_id is not None else []
        extra_values = [parent_id] if parent_id is not None else []
    count_sql = (
        'SELECT ' + node_select + ',COUNT(DISTINCT q.id) AS question_count,'
        'COUNT(DISTINCT CASE WHEN l.is_primary=1 THEN q.id END) AS primary_question_count '
        'FROM question q '
        'JOIN question_knowledge_point l ON l.question_id=q.id AND l.deleted=0 '
        'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 AND k.level=2 '
        'JOIN knowledge_point m ON m.id=k.parent_id AND m.deleted=0 AND m.level=1 '
        'JOIN subject s ON s.id=m.subject_id AND s.deleted=0 '
        'WHERE ' + ' AND '.join(question_where + node_where) + ' GROUP BY ' + node_group)
    counts = await db.all(count_sql, [*question_values, *extra_values])
    practice_sql = (
        'SELECT ' + node_select + ',COUNT(DISTINCT pq.id) AS answer_count,'
        'COUNT(DISTINCT CASE WHEN pq.is_correct=1 THEN pq.id END) AS correct_count '
        'FROM practice_set_question pq '
        "JOIN practice_set p ON p.id=pq.practice_set_id AND p.deleted=0 AND p.reviewed=1 AND p.source_type='question' "
        'JOIN question q ON q.id=pq.question_id AND q.deleted=0 '
        'JOIN question_knowledge_point l ON l.question_id=q.id AND l.deleted=0 '
        'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 AND k.level=2 '
        'JOIN knowledge_point m ON m.id=k.parent_id AND m.deleted=0 AND m.level=1 '
        'JOIN subject s ON s.id=m.subject_id AND s.deleted=0 '
        'WHERE ' + ' AND '.join(practice_where + node_where) + ' GROUP BY ' + node_group)
    practice = await db.all(practice_sql, [*practice_values, *extra_values])
    # 覆盖率分母使用收录筛选后的题目集合，分子必须是同一集合内“曾有过有效批改”的题；
    # 不叠加练习批改时间，避免旧题本期复习把覆盖率放大到 100% 以上。
    coverage_sql = (
        'SELECT ' + node_select + ',COUNT(DISTINCT q.id) AS reviewed_question_count '
        'FROM question q '
        'JOIN question_knowledge_point l ON l.question_id=q.id AND l.deleted=0 '
        'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 AND k.level=2 '
        'JOIN knowledge_point m ON m.id=k.parent_id AND m.deleted=0 AND m.level=1 '
        'JOIN subject s ON s.id=m.subject_id AND s.deleted=0 '
        'JOIN practice_set_question pq ON pq.question_id=q.id AND pq.deleted=0 AND pq.is_correct IS NOT NULL '
        "JOIN practice_set p ON p.id=pq.practice_set_id AND p.deleted=0 AND p.reviewed=1 AND p.source_type='question' "
        'WHERE ' + ' AND '.join(question_where + node_where) + ' GROUP BY ' + node_group)
    coverage = await db.all(coverage_sql, [*question_values, *extra_values])
    coverage_map = {row['id']: row['reviewed_question_count'] or 0 for row in coverage}
    nodes = {}
    for row in directory:
        nodes[row['id']] = {**row, 'question_count': 0, 'primary_question_count': 0,
                            'answer_count': 0, 'correct_count': 0, 'reviewed_question_count': 0}
    for row in counts:
        node = nodes.setdefault(row['id'], {**row, 'answer_count': 0, 'correct_count': 0,
                                            'reviewed_question_count': 0})
        node.update(question_count=row['question_count'] or 0,
                    primary_question_count=row['primary_question_count'] or 0)
    for row in practice:
        node = nodes.setdefault(row['id'], {**row, 'question_count': 0, 'primary_question_count': 0})
        node.update(answer_count=row['answer_count'] or 0, correct_count=row['correct_count'] or 0)
    for node_id, reviewed in coverage_map.items():
        if node_id in nodes:
            nodes[node_id]['reviewed_question_count'] = reviewed
    total_row = await db.first(
        'SELECT COUNT(*) AS total,SUM(CASE WHEN EXISTS('
        'SELECT 1 FROM question_knowledge_point l JOIN knowledge_point k '
        'ON k.id=l.knowledge_point_id AND k.deleted=0 AND k.level=2 '
        'WHERE l.question_id=q.id AND l.deleted=0) THEN 0 ELSE 1 END) AS unclassified '
        'FROM question q WHERE ' + ' AND '.join(question_where), question_values)
    total = total_row['total'] or 0
    unclassified = total_row['unclassified'] or 0
    items = []
    for node in nodes.values():
        answer_count = node['answer_count']
        correct_count = node['correct_count']
        question_count = node['question_count']
        primary_count = node['primary_question_count']
        reviewed_questions = node['reviewed_question_count']
        items.append({
            'id': node['id'],
            'name': node['name'],
            'level': node['level'],
            'parent_id': node['parent_id'],
            'parent_name': node['parent_name'],
            'subject_id': node['subject_id'],
            'subject_name': node['subject_name'],
            'question_count': question_count,
            'primary_question_count': primary_count,
            'share_percent': round(primary_count * 100.0 / total, 1) if total else 0.0,
            'reviewed_question_count': reviewed_questions,
            'review_coverage': round(reviewed_questions * 100.0 / question_count, 1) if question_count else None,
            'answer_count': answer_count,
            'correct_count': correct_count,
            'accuracy': round(correct_count * 100.0 / answer_count, 1) if answer_count else None,
        })
    if level == 2:
        parent_total = None
        if parent_id is not None:
            parent_row = await db.first(
                'SELECT COUNT(DISTINCT q.id) AS total '
                'FROM question q '
                'JOIN question_knowledge_point l ON l.question_id=q.id AND l.deleted=0 '
                'JOIN knowledge_point k ON k.id=l.knowledge_point_id AND k.deleted=0 AND k.level=2 '
                'JOIN knowledge_point m ON m.id=k.parent_id AND m.deleted=0 AND m.level=1 '
                'WHERE m.id=? AND ' + ' AND '.join(question_where), [parent_id, *question_values])
            parent_total = parent_row['total'] or 0
        for item in items:
            item['parent_share_percent'] = (
                round(item['primary_question_count'] * 100.0 / parent_total, 1)
                if parent_total else None)
    items.sort(key=lambda item: (-item['question_count'], item['id']))
    return {
        'taxonomy_version': await taxonomy_version(db),
        'counting_mode': COUNTING_MODE,
        'level': level,
        'parent_id': parent_id,
        'total_questions': total,
        'unclassified_count': unclassified,
        'items': items,
    }


async def knowledge_options(db, subject_id=None):
    """从目录读取筛选项，不再依赖题目文本去重。"""
    filters, values = ['deleted=0', 'level IN (1,2)'], []
    if subject_id is not None:
        filters.append('subject_id=?')
        values.append(subject_id)
    rows = await db.all('SELECT id,name,level,parent_id,code,sort_order FROM knowledge_point WHERE '
                        + ' AND '.join(filters) + ' ORDER BY level,sort_order,id', values)
    parents = {row['id']: row['name'] for row in rows if row.get('level') == 1}
    return [{
        'id': row['id'],
        'name': row['name'],
        'level': row['level'],
        'parent_id': row['parent_id'],
        'parent_name': parents.get(row['parent_id']),
        'code': row.get('code'),
        'sort_order': row.get('sort_order') or 0,
    } for row in rows]


async def validate_filter_ids(db, subject_id=None, parent_id=None, point_id=None):
    """校验一级/二级筛选组合属于同一路径，非法组合返回 422。"""
    point = None
    if point_id is not None:
        point = await db.first(
            'SELECT id,level,parent_id,subject_id FROM knowledge_point WHERE id=? AND deleted=0', (point_id,))
        if not point or point.get('level') != 2:
            raise HTTPException(422, '二级知识点筛选无效')
        if subject_id is not None and point.get('subject_id') != subject_id:
            raise HTTPException(422, '知识点与学科不匹配')
        if parent_id is not None and point.get('parent_id') != parent_id:
            raise HTTPException(422, '一级与二级知识点不属于同一路径')
    elif parent_id is not None:
        parent = await db.first(
            'SELECT id,level,subject_id FROM knowledge_point WHERE id=? AND deleted=0', (parent_id,))
        if not parent or parent.get('level') != 1:
            raise HTTPException(422, '一级知识点筛选无效')
        if subject_id is not None and parent.get('subject_id') != subject_id:
            raise HTTPException(422, '知识点与学科不匹配')
    return parent_id, point_id
