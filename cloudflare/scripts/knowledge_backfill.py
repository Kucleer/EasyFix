"""按已审核映射生成幂等的知识点回填 SQL，不直接写生产库。

默认只做校验并输出 SQL 到 tmp/；执行仍由维护窗口内的受控 Wrangler 命令完成。

    python cloudflare/scripts/knowledge_backfill.py \
        --seed cloudflare/scripts/knowledge_seed_modules.json \
        --mapping tmp/knowledge-reviewed-mapping.json \
        --snapshot backups/.../database.sqlite3

映射格式见文档 docs/knowledge-hierarchy-implementation-notes.md。
"""

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from knowledge_model import normalize_name_key  # noqa: E402
from knowledge_tools import connect, load_json, rows, scalar, write_text  # noqa: E402


def quote(value):
    """生成 SQL 文本字面量。"""
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def point_key(subject, level, name, parent_code=None):
    """用于映射内判重的键。"""
    return (subject, level, None if level == 1 else parent_code, normalize_name_key(name))


def attach_existing(points, connection):
    """把可以复用的旧目录行绑定到映射项，保留原 ID，避免同级重名冲突。"""
    for item in points:
        item.pop('existing_id', None)
        if not connection:
            continue
        subject_id = scalar(connection, 'SELECT id FROM subject WHERE name=? AND deleted=0', (item.get('subject'),))
        if not subject_id:
            continue
        candidates = rows(connection, """
            SELECT id,code,deleted,level,parent_id,name FROM knowledge_point
             WHERE subject_id=? AND deleted=0""", (subject_id,))
        wanted = normalize_name_key(item['name'])
        compatible = [row for row in candidates
                      if normalize_name_key(row.get('name')) == wanted
                      and row['level'] in (None, item['level'])]
        if len(compatible) > 1:
            item['_error'] = '同名旧目录行不唯一：' + item['code']
            continue
        if not compatible:
            continue
        row = compatible[0]
        if row['code'] and row['code'] != item['code']:
            item['_error'] = '同名旧目录行已有其他编码 ' + str(row['code']) + '：' + item['code']
            continue
        if item['level'] == 1 and row['level'] == 1 and row['parent_id'] is not None:
            item['_error'] = '同名旧目录行是带父级的一级：' + item['code']
            continue
        if item['level'] == 2 and row['parent_id'] is not None:
            parent_code = scalar(connection, 'SELECT code FROM knowledge_point WHERE id=?', (row['parent_id'],))
            if parent_code and parent_code != item.get('parent_code'):
                item['_error'] = '同名旧目录行的父级编码不匹配：' + item['code']
                continue
        item['existing_id'] = row['id']


def validate(points, questions, connection):
    """校验种子目录与逐题映射，返回错误列表。"""
    errors = []
    subjects = {row['name'] for row in rows(connection, 'SELECT name FROM subject WHERE deleted=0')} if connection else set()
    codes = {}
    keys = {}
    for item in points:
        code = item.get('code')
        name = item.get('name')
        level = item.get('level')
        subject = item.get('subject')
        if not code or not name or level not in (1, 2) or not subject:
            errors.append('目录项缺少 code/name/level/subject：' + json.dumps(item, ensure_ascii=False))
            continue
        if code in codes:
            errors.append('目录编码重复：' + code)
        codes[code] = item
        if subjects and subject not in subjects:
            errors.append('学科不存在：' + subject + '（' + code + '）')
        key = point_key(subject, level, name, item.get('parent_code'))
        if key in keys:
            errors.append('同级同名目录项：' + name + '（' + code + ' 与 ' + keys[key] + '）')
        keys[key] = code
    for item in points:
        if item.get('level') == 2:
            parent = codes.get(item.get('parent_code'))
            if not parent or parent.get('level') != 1 or parent.get('subject') != item.get('subject'):
                errors.append('二级缺少同科目一级：' + str(item.get('code')))
    attach_existing(points, connection)
    for item in points:
        if item.get('_error'):
            errors.append(item['_error'])
    if connection:
        existing = {row['code']: row for row in rows(
            connection, 'SELECT code,deleted FROM knowledge_point WHERE code IS NOT NULL')}
        for code in codes:
            if code in existing and existing[code]['deleted'] and not codes[code].get('existing_id'):
                errors.append('编码已存在于软删除目录行，需人工确认恢复：' + code)
    seen = set()
    for item in questions:
        question_id = item.get('question_id')
        if type(question_id) is not int:
            errors.append('题目 ID 无效：' + json.dumps(item, ensure_ascii=False))
            continue
        if question_id in seen:
            errors.append('题目重复映射：' + str(question_id))
        seen.add(question_id)
        if type(item.get('knowledge_revision')) is not int:
            errors.append('题目 ' + str(question_id) + ' 缺少 knowledge_revision')
        item_codes = item.get('codes') or []
        if not item_codes:
            errors.append('题目 ' + str(question_id) + ' 没有目标二级')
        if item.get('primary_code') not in item_codes:
            errors.append('题目 ' + str(question_id) + ' 的主考点不在目标列表中')
        if len(set(item_codes)) != len(item_codes):
            errors.append('题目 ' + str(question_id) + ' 的知识点编码重复')
        for code in item_codes:
            point = codes.get(code)
            if not point or point.get('level') != 2:
                errors.append('题目 ' + str(question_id) + ' 引用了非二级或未知编码：' + str(code))
        if connection:
            if not scalar(connection, 'SELECT COUNT(*) FROM question WHERE id=? AND deleted=0', (question_id,)):
                errors.append('题目不存在或已删除：' + str(question_id))
    return errors


def point_sql(item, stamp, subject_id):
    """生成按 code 幂等插入的目录 SQL。"""
    code = quote(item['code'])
    name = quote(item['name'])
    name_key = quote(normalize_name_key(item['name']))
    subject = subject_id or ('(SELECT id FROM subject WHERE name=' + quote(item['subject']) + ' AND deleted=0)')
    parent = 'NULL'
    if item.get('level') == 2:
        parent = ('(SELECT id FROM knowledge_point WHERE code=' + quote(item.get('parent_code'))
                  + ' AND deleted=0)')
    sort_order = int(item.get('sort_order') or 0)
    grade = quote(item.get('grade'))
    semester = quote(item.get('semester'))
    inserted_id = item.get('id')
    id_sql = str(int(inserted_id)) if inserted_id else '(SELECT COALESCE(MAX(id),0)+1 FROM knowledge_point)'
    if item.get('existing_id'):
        return (
            '-- 复用旧目录：' + item['code'] + ' ' + item['name'] + ' -> id ' + str(item['existing_id']) + '\n'
            'UPDATE knowledge_point SET code=' + code + ',name=' + name + ',name_key=' + name_key
            + ',subject_id=' + str(subject) + ',level=' + str(int(item['level']))
            + ',parent_id=' + parent + ',sort_order=' + str(sort_order) + ',grade=' + grade
            + ',semester=' + semester + ',deleted=0,updated_at=' + quote(stamp)
            + ' WHERE id=' + str(int(item['existing_id'])) + ' AND deleted=0;\n'
        )
    return (
        '-- 目录：' + item['code'] + ' ' + item['name'] + '\n'
        'INSERT INTO knowledge_point(id,code,name,name_key,subject_id,level,parent_id,sort_order,grade,semester,deleted,created_at,updated_at)\n'
        'SELECT ' + id_sql + ',' + code + ',' + name + ',' + name_key + ',' + str(subject) + ','
        + str(int(item['level'])) + ',' + parent + ',' + str(sort_order) + ',' + grade + ',' + semester
        + ",0," + quote(stamp) + ',' + quote(stamp) + '\n'
        ' WHERE NOT EXISTS(SELECT 1 FROM knowledge_point WHERE code=' + code + ');\n'
    )


def question_sql(item, stamp, name_by_code):
    """生成单题的分类回填 SQL（调用方负责事务与断言）。"""
    question_id = int(item['question_id'])
    lines = ['-- 题目 ' + str(question_id) + '\n',
             'UPDATE question SET knowledge_revision=knowledge_revision+1,knowledge_point='
             + quote(name_by_code.get(item['primary_code'])) + ',updated_at=' + quote(stamp)
             + ' WHERE id=' + str(question_id) + ' AND deleted=0;\n',
             'UPDATE question_knowledge_point SET deleted=1,is_primary=0 WHERE question_id='
             + str(question_id) + ';\n']
    for code in item['codes']:
        primary = 1 if code == item['primary_code'] else 0
        lines.append(
            'INSERT INTO question_knowledge_point(question_id,knowledge_point_id,is_primary,source,deleted,created_at,updated_at)\n'
            'SELECT ' + str(question_id) + ',id,' + str(primary) + ",'migration',0,"
            + quote(stamp) + ',' + quote(stamp)
            + ' FROM knowledge_point WHERE code=' + quote(code) + ' AND deleted=0\n'
            ' ON CONFLICT(question_id,knowledge_point_id) DO UPDATE SET deleted=0,is_primary=excluded.is_primary,'
            'source=excluded.source,updated_at=excluded.updated_at;\n')
    return ''.join(lines)


def assertion_sql(items):
    """生成批次内的版本、目标集合与结构断言。

    结构断言同时校验：实际关联数量等于审核 codes、没有额外关联、恰好一个主考点、
    主考点编码等于审核 primary。任一不符都会使整个批次回滚。
    """
    state = json.dumps([{
        'id': int(item['question_id']),
        'revision': int(item['knowledge_revision']),
        'codes': list(item['codes']),
        'primary': item['primary_code'],
    } for item in items], ensure_ascii=False)
    all_codes = sorted({code for item in items for code in item['codes']})
    code_list = ','.join(quote(code) for code in all_codes) if all_codes else "''"
    question_id = "json_extract(j.value,'$.id')"
    codes_json = "json_extract(j.value,'$.codes')"
    primary = "json_extract(j.value,'$.primary')"
    guard = (
        'UPDATE knowledge_assert SET guard=CASE WHEN EXISTS(SELECT 1 FROM write_guard WHERE id=1 AND deleted=0) '
        'AND (SELECT COUNT(*) FROM knowledge_point WHERE deleted=0 AND level=2 AND code IN (' + code_list + ')) = '
        + str(len(all_codes)) + ' '
        "AND NOT EXISTS(SELECT 1 FROM json_each(" + quote(state) + ") j WHERE COALESCE("
        "(SELECT knowledge_revision FROM question WHERE id=" + question_id + " AND deleted=0),-1)"
        "<>json_extract(j.value,'$.revision')) THEN 1 ELSE NULL END WHERE id=1;\n")
    structure = (
        'UPDATE knowledge_assert SET structure=CASE WHEN NOT EXISTS(SELECT 1 FROM json_each('
        + quote(state) + ') j WHERE '
        '(SELECT COUNT(*) FROM question_knowledge_point l JOIN knowledge_point k ON k.id=l.knowledge_point_id '
        'WHERE l.question_id=' + question_id + ' AND l.deleted=0) <> json_array_length(' + codes_json + ') '
        'OR EXISTS(SELECT 1 FROM question_knowledge_point l JOIN knowledge_point k ON k.id=l.knowledge_point_id '
        'WHERE l.question_id=' + question_id + ' AND l.deleted=0 AND NOT EXISTS('
        'SELECT 1 FROM json_each(' + codes_json + ') c WHERE c.value=k.code)) '
        'OR (SELECT COUNT(*) FROM question_knowledge_point l WHERE l.question_id=' + question_id
        + ' AND l.deleted=0 AND l.is_primary=1) <> 1 '
        'OR NOT EXISTS(SELECT 1 FROM question_knowledge_point l JOIN knowledge_point k ON k.id=l.knowledge_point_id '
        'WHERE l.question_id=' + question_id + ' AND l.deleted=0 AND l.is_primary=1 AND k.code=' + primary + ') '
        ') THEN 1 ELSE NULL END WHERE id=1;\n')
    return guard, structure


def main():
    """校验映射并生成可审阅的 SQL。"""
    parser = argparse.ArgumentParser(description='生成两级知识点幂等回填 SQL')
    parser.add_argument('--mapping', required=True, help='已审核的目录与逐题映射 JSON')
    parser.add_argument('--seed', default='', help='可选的一级模块种子 JSON')
    parser.add_argument('--snapshot', default='', help='可选：D1 导出的 SQLite 快照，用于交叉校验')
    parser.add_argument('--out', default='')
    parser.add_argument('--batch-size', type=int, default=25)
    arguments = parser.parse_args()
    mapping = load_json(arguments.mapping)
    points = []
    if arguments.seed:
        points.extend(load_json(arguments.seed).get('points', []))
    points.extend(mapping.get('points', []))
    points.sort(key=lambda item: (item.get('level') or 2,))
    questions = mapping.get('questions', [])
    connection = connect(arguments.snapshot) if arguments.snapshot else None
    errors = validate(points, questions, connection)
    if errors:
        for error in errors:
            print('错误：' + error)
        raise SystemExit(1)
    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    name_by_code = {item['code']: item['name'] for item in points}
    output = Path(arguments.out) if arguments.out else (
        ROOT / 'tmp' / ('knowledge-backfill-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S')))
    output.mkdir(parents=True, exist_ok=True)
    # D1 导入不支持 BEGIN/COMMIT，批次文件按“守卫 → 写入 → 结构断言”顺序单独执行。
    catalog = ['-- 目录与错误类型；可重复执行。\n']
    for item in points:
        catalog.append(point_sql(item, stamp, item.get('subject_id')))
    for item in points:
        if item.get('level') == 2 and item.get('error_type_ids'):
            for error_type_id in item['error_type_ids']:
                catalog.append('INSERT INTO kp_error_type(knowledge_point_id,error_type_id,deleted)\n'
                               'SELECT id,' + str(int(error_type_id)) + ',0 FROM knowledge_point WHERE code='
                               + quote(item['code']) + ' AND deleted=0\n'
                               " ON CONFLICT(knowledge_point_id,error_type_id) DO UPDATE SET deleted=0;\n")
    files = []
    catalog_path = write_text(output / '00-catalog.sql', ''.join(catalog))
    files.append(catalog_path)
    size = max(1, arguments.batch_size)
    for offset in range(0, len(questions), size):
        batch = questions[offset:offset + size]
        guard, structure = assertion_sql(batch)
        text = ['-- 批次 ' + str(offset // size + 1) + '：' + str(len(batch)) + ' 道题\n', guard]
        for item in batch:
            text.append(question_sql(item, stamp, name_by_code))
        text.append(structure)
        path = write_text(output / ('batch-%03d.sql' % (offset // size + 1)), ''.join(text))
        files.append(path)
    versions = ('-- 目录版本递增；全部批次通过一致性校验后再执行。\n'
                "INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES('taxonomy_version','1',0,CURRENT_TIMESTAMP)\n"
                "ON CONFLICT(name) DO UPDATE SET value=CAST(CAST(runtime_config.value AS INTEGER)+1 AS TEXT),\n"
                "deleted=0,updated_at=excluded.updated_at;\n"
                "UPDATE runtime_config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) "
                "WHERE name='data_revision' AND deleted=0;\n")
    files.append(write_text(output / '99-versions.sql', versions))
    manifest = {
        'generated_at': stamp,
        'mapping': str(Path(arguments.mapping).resolve()),
        'mapping_sha256': hashlib.sha256(Path(arguments.mapping).read_bytes()).hexdigest(),
        'seed': str(Path(arguments.seed).resolve()) if arguments.seed else None,
        'snapshot': str(Path(arguments.snapshot).resolve()) if arguments.snapshot else None,
        'points': len(points),
        'questions': len(questions),
        'files': [{'name': path.name, 'bytes': path.stat().st_size,
                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in files],
        'order': [path.name for path in files],
        'note': 'D1 导入不支持显式事务；请逐批执行，每批后运行一致性校验（含 --mapping）核对集合。',
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    print('已生成回填目录：' + str(output))
    print('目录项 %s，题目映射 %s，批次 %s' % (
        len(points), len(questions), (len(questions) + size - 1) // size))
    print('执行顺序（维护窗口、已记录 Time Travel 书签并完成备份后逐批执行）：')
    for path in files:
        print('  node cloudflare/tools/cli.cjs d1 execute easyfix --config cloudflare/wrangler.jsonc '
              '--remote --file ' + str(path) + ' --yes')
        if path.name.startswith('batch-'):
            print('    # 本批完成后立即运行：python cloudflare/scripts/knowledge_consistency_check.py --snapshot <新导出>')


if __name__ == '__main__':
    main()
