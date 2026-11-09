"""两级知识点迁移后一致性校验（只读）。

对 D1 导出的 SQLite 快照运行约束审计；发现违规时以非零状态退出，
用于部署后及每批回填后停止继续迁移。

    python cloudflare/scripts/knowledge_consistency_check.py --snapshot backups/.../database.sqlite3
"""

import argparse
import datetime
from pathlib import Path

from knowledge_tools import columns, connect, load_json, require_columns, rows, scalar, write_json

ROOT = Path(__file__).resolve().parents[2]

CHECKS = [
    ('qkp_invalid_target', 'error', """
        SELECT COUNT(*) AS count FROM question_knowledge_point l
         WHERE l.deleted=0 AND NOT EXISTS(
           SELECT 1 FROM question q JOIN knowledge_point k ON k.id=l.knowledge_point_id
            WHERE q.id=l.question_id AND q.deleted=0 AND k.deleted=0 AND k.level=2
              AND k.subject_id=q.subject_id)"""),
    ('qkp_orphan_question', 'error', """
        SELECT COUNT(*) AS count FROM question_knowledge_point l
         WHERE l.deleted=0 AND NOT EXISTS(SELECT 1 FROM question q WHERE q.id=l.question_id)"""),
    ('primary_count_mismatch', 'error', """
        SELECT COUNT(*) AS count FROM (
          SELECT q.id,
                 (SELECT COUNT(*) FROM question_knowledge_point l
                   WHERE l.question_id=q.id AND l.deleted=0 AND l.is_primary=1) AS primaries,
                 (SELECT COUNT(*) FROM question_knowledge_point l
                   WHERE l.question_id=q.id AND l.deleted=0) AS links
            FROM question q WHERE q.deleted=0)
         WHERE (links>0 AND primaries<>1) OR (links=0 AND primaries<>0)"""),
    ('level2_invalid_parent', 'error', """
        SELECT COUNT(*) AS count FROM knowledge_point k
         WHERE k.deleted=0 AND k.level=2 AND NOT EXISTS(
           SELECT 1 FROM knowledge_point p WHERE p.id=k.parent_id AND p.deleted=0 AND p.level=1
             AND p.subject_id=k.subject_id)"""),
    ('level1_has_parent', 'error', """
        SELECT COUNT(*) AS count FROM knowledge_point
         WHERE deleted=0 AND level=1 AND parent_id IS NOT NULL"""),
    ('invalid_level', 'error', """
        SELECT COUNT(*) AS count FROM knowledge_point
         WHERE deleted=0 AND level IS NOT NULL AND level NOT IN (1,2)"""),
    ('missing_name_key', 'error', """
        SELECT COUNT(*) AS count FROM knowledge_point
         WHERE deleted=0 AND level IS NOT NULL
           AND (name_key IS NULL OR TRIM(name_key)='' OR TRIM(name)='')"""),
    ('duplicate_level1', 'error', """
        SELECT COUNT(*) AS count FROM (
          SELECT subject_id,name_key FROM knowledge_point WHERE deleted=0 AND level=1
           GROUP BY subject_id,name_key HAVING COUNT(*)>1)"""),
    ('duplicate_level2', 'error', """
        SELECT COUNT(*) AS count FROM (
          SELECT parent_id,name_key FROM knowledge_point WHERE deleted=0 AND level=2
           GROUP BY parent_id,name_key HAVING COUNT(*)>1)"""),
    ('error_type_on_non_level2', 'error', """
        SELECT COUNT(*) AS count FROM kp_error_type e
         WHERE e.deleted=0 AND EXISTS(
           SELECT 1 FROM knowledge_point k
            WHERE k.id=e.knowledge_point_id AND k.deleted=0
              AND k.level IS NOT NULL AND k.level<>2)"""),
    ('legacy_error_type_rows', 'warning', """
        SELECT COUNT(*) AS count FROM kp_error_type e
         WHERE e.deleted=0 AND EXISTS(
           SELECT 1 FROM knowledge_point k
            WHERE k.id=e.knowledge_point_id AND k.deleted=0 AND k.level IS NULL)"""),
    ('error_type_with_deleted_kp', 'warning', """
        SELECT COUNT(*) AS count FROM kp_error_type e
         WHERE e.deleted=0 AND NOT EXISTS(
           SELECT 1 FROM knowledge_point k WHERE k.id=e.knowledge_point_id AND k.deleted=0)"""),
    ('deleted_level1_with_children', 'error', """
        SELECT COUNT(*) AS count FROM knowledge_point p
         WHERE p.deleted=1 AND p.level=1 AND EXISTS(
           SELECT 1 FROM knowledge_point c WHERE c.parent_id=p.id AND c.deleted=0)"""),
    ('deleted_level2_with_links', 'error', """
        SELECT COUNT(*) AS count FROM knowledge_point k
         WHERE k.deleted=1 AND k.level=2 AND EXISTS(
           SELECT 1 FROM question_knowledge_point l JOIN question q
             ON q.id=l.question_id AND q.deleted=0
            WHERE l.knowledge_point_id=k.id AND l.deleted=0)"""),
    ('orphan_question_link_rows', 'warning', """
        SELECT COUNT(*) AS count FROM question_knowledge_point l
         WHERE l.deleted=0 AND NOT EXISTS(SELECT 1 FROM question q WHERE q.id=l.question_id AND q.deleted=0)"""),
    ('missing_legacy_text', 'warning', """
        SELECT COUNT(*) AS count FROM question
         WHERE deleted=0 AND knowledge_point IS NOT NULL AND knowledge_point<>''
           AND (legacy_knowledge_point IS NULL OR legacy_knowledge_point='')"""),
    ('soft_deleted_subject_in_use', 'warning', """
        SELECT COUNT(*) AS count FROM subject s
         WHERE s.deleted=1 AND (EXISTS(
           SELECT 1 FROM knowledge_point k WHERE k.subject_id=s.id AND k.deleted=0 AND k.level IS NOT NULL)
           OR EXISTS(SELECT 1 FROM question q WHERE q.subject_id=s.id AND q.deleted=0))"""),
]


def main():
    """运行一致性校验并输出报告。"""
    parser = argparse.ArgumentParser(description='两级知识点一致性校验（只读）')
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--mapping', default='', help='可选：审核映射 JSON，逐题核对实际关联集合与主考点')
    parser.add_argument('--out', default='')
    arguments = parser.parse_args()
    connection = connect(arguments.snapshot)
    require_columns(connection, 'knowledge_point', ('name_key', 'level', 'parent_id', 'sort_order'))
    require_columns(connection, 'question', ('knowledge_revision', 'legacy_knowledge_point'))
    report = {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'snapshot': str(Path(arguments.snapshot).resolve()), 'results': [], 'errors': [], 'warnings': []}
    for name, severity, sql in CHECKS:
        count = scalar(connection, sql) or 0
        report['results'].append({'name': name, 'severity': severity, 'count': count})
        if count and severity == 'error':
            report['errors'].append(name + ': ' + str(count))
        elif count:
            report['warnings'].append(name + ': ' + str(count))
    if arguments.mapping:
        mapping = load_json(arguments.mapping)
        mismatches = []
        for item in mapping.get('questions', []):
            active = rows(connection, """
                SELECT k.code,k.deleted AS kp_deleted,l.is_primary
                  FROM question_knowledge_point l
                  JOIN knowledge_point k ON k.id=l.knowledge_point_id
                 WHERE l.question_id=? AND l.deleted=0""", (item.get('question_id'),))
            actual = sorted(row['code'] for row in active
                            if row['code'] and not row['kp_deleted'])
            expected = sorted(set(item.get('codes') or []))
            primary = next((row['code'] for row in active
                            if row['is_primary'] and not row['kp_deleted']), None)
            if actual != expected or primary != item.get('primary_code'):
                mismatches.append({'question_id': item.get('question_id'),
                                   'expected': expected, 'actual': actual,
                                   'expected_primary': item.get('primary_code'),
                                   'actual_primary': primary})
        report['mapping'] = {'questions': len(mapping.get('questions', [])),
                             'mismatches': mismatches}
        if mismatches:
            report['errors'].append('mapping_mismatch: ' + str(len(mismatches)))
    report['schema'] = {
        'has_table_qkp': bool(scalar(connection,
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='question_knowledge_point'")),
        'has_primary_index': bool(scalar(connection,
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name='ux_qkp_primary'")),
        'triggers': [row['name'] for row in rows(connection,
            "SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name")],
        'write_guard': scalar(connection, 'SELECT revision FROM write_guard WHERE id=1 AND deleted=0'),
        'knowledge_assert': scalar(connection, 'SELECT COUNT(*) FROM knowledge_assert WHERE id=1'),
        'taxonomy_version': scalar(connection, "SELECT value FROM runtime_config WHERE name='taxonomy_version' AND deleted=0"),
    }
    for key in ('has_table_qkp', 'has_primary_index'):
        if not report['schema'][key]:
            report['errors'].append('schema 缺少 ' + key)
    if report['schema']['write_guard'] is None:
        report['errors'].append('write_guard 守卫行缺失')
    if not report['schema']['knowledge_assert']:
        report['errors'].append('knowledge_assert 断言行缺失')
    if report['schema']['taxonomy_version'] in (None, ''):
        report['errors'].append('taxonomy_version 未写入')
    required_triggers = ('trg_kp_bi', 'trg_kp_bu', 'trg_qkp_bi', 'trg_qkp_bu',
                         'trg_question_subject_kp', 'trg_kp_error_type_bi',
                         'trg_subject_bu', 'trg_knowledge_assert_guard',
                         'trg_knowledge_assert_structure')
    missing = [name for name in required_triggers if name not in report['schema']['triggers']]
    if missing:
        report['errors'].append('缺少触发器：' + ', '.join(missing))
    output = arguments.out or str(ROOT / 'tmp' / ('knowledge-consistency-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S') + '.json'))
    path = write_json(output, report)
    print('一致性校验完成：' + str(path))
    for item in report['results']:
        if item['count']:
            print('%-32s %-8s %s' % (item['name'], item['severity'], item['count']))
    if report['errors']:
        print('错误：' + '；'.join(report['errors']))
        raise SystemExit(1)
    print('未发现阻断性违规')


if __name__ == '__main__':
    main()
