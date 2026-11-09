"""两级知识点迁移前只读预检。

输入为 D1 导出的 SQLite 快照（例如
`backups/cloudflare_d1_20261109T023329946287Z/database.sqlite3`），输出到 tmp/。
默认不写数据库、不调用模型。

    python cloudflare/scripts/knowledge_preflight.py --snapshot backups/.../database.sqlite3
"""

import argparse
import datetime
from pathlib import Path

from knowledge_tools import (columns, connect, inventory, load_json, require_columns, rows,
                             scalar, table_exists, write_json)

ROOT = Path(__file__).resolve().parents[2]


def candidate_duplicates(connection):
    """检查同一学科/父级下规范化键重复的目录行。"""
    if 'name_key' not in columns(connection, 'knowledge_point'):
        return []
    return rows(connection, """
        SELECT level,subject_id,parent_id,name_key,COUNT(*) AS count,GROUP_CONCAT(name,'|') AS names
          FROM knowledge_point WHERE deleted=0 AND level IS NOT NULL
         GROUP BY level,subject_id,parent_id,name_key HAVING COUNT(*)>1
         ORDER BY count DESC""")


def legacy_texts(connection):
    """统计旧文本标签，并给出当前唯一匹配的二级候选。"""
    data = rows(connection, """
        SELECT q.subject_id,s.name AS subject_name,TRIM(q.knowledge_point) AS text,COUNT(*) AS question_count
          FROM question q JOIN subject s ON s.id=q.subject_id AND s.deleted=0
         WHERE q.deleted=0 AND q.knowledge_point IS NOT NULL AND TRIM(q.knowledge_point)<>''
         GROUP BY q.subject_id,TRIM(q.knowledge_point) ORDER BY question_count DESC,s.name""")
    if 'level' not in columns(connection, 'knowledge_point'):
        for item in data:
            item['candidate_ids'] = []
            item['status'] = 'pending_level_backfill'
        return data
    for item in data:
        matches = rows(connection, """
            SELECT k.id,k.name FROM knowledge_point k
             WHERE k.deleted=0 AND k.level=2 AND k.subject_id=? AND k.name_key=?""",
                       (item['subject_id'], normalize(item['text'])))
        item['candidate_ids'] = [match['id'] for match in matches]
        if len(matches) == 1:
            item['status'] = 'unique'
        elif matches:
            item['status'] = 'ambiguous'
        else:
            item['status'] = 'unmatched'
    return data


def normalize(text):
    """与业务一致的规范键，迁移后由应用层写入 name_key。"""
    import re
    import unicodedata
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text).strip()).casefold()


def wide_labels(items):
    """列出过宽或复合的旧标签，必须人工细分，不能自动猜测。"""
    result = []
    for item in items:
        text = item['text'] or ''
        if any(mark in text for mark in ('、', '/', '，', ',', '与', '和')) or len(text) > 12:
            result.append(item)
    return result


def main():
    """执行只读预检并输出 JSON 报告。"""
    parser = argparse.ArgumentParser(description='两级知识点迁移前只读预检')
    parser.add_argument('--snapshot', required=True, help='D1 导出的 SQLite 快照路径')
    parser.add_argument('--out', default='', help='输出 JSON 路径，默认写入 tmp/')
    parser.add_argument('--seed', default='', help='可选：已审核的种子目录 JSON')
    arguments = parser.parse_args()
    connection = connect(arguments.snapshot)
    report = {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'snapshot': str(Path(arguments.snapshot).resolve()), 'errors': [], 'warnings': []}
    report['tables'] = {
        'subject': scalar(connection, 'SELECT COUNT(*) FROM subject WHERE deleted=0'),
        'question': scalar(connection, 'SELECT COUNT(*) FROM question WHERE deleted=0'),
        'knowledge_point': scalar(connection, 'SELECT COUNT(*) FROM knowledge_point WHERE deleted=0'),
    }
    report['question_distribution'] = rows(connection, """
        SELECT subject_id,grade,semester,COUNT(*) AS count FROM question WHERE deleted=0
         GROUP BY subject_id,grade,semester ORDER BY subject_id,grade,semester""")
    report['knowledge_point_columns'] = columns(connection, 'knowledge_point')
    report['question_columns'] = columns(connection, 'question')
    report['schema'] = {table: inventory(connection, table)
                        for table in ('knowledge_point', 'question', 'question_knowledge_point',
                                      'kp_error_type', 'write_guard', 'knowledge_assert')}
    report['legacy_texts'] = legacy_texts(connection)
    report['wide_labels'] = wide_labels(report['legacy_texts'])
    report['duplicate_candidates'] = candidate_duplicates(connection)
    if 'level' in report['knowledge_point_columns']:
        require_columns(connection, 'knowledge_point', ('name_key', 'level', 'parent_id', 'sort_order'))
        report['levels'] = rows(connection, """
            SELECT COALESCE(level,-1) AS level,COUNT(*) AS count FROM knowledge_point
             WHERE deleted=0 GROUP BY COALESCE(level,-1) ORDER BY level""")
        report['invalid_nodes'] = {
            'level2_without_parent': scalar(connection, """
                SELECT COUNT(*) FROM knowledge_point k WHERE k.deleted=0 AND k.level=2 AND NOT EXISTS(
                  SELECT 1 FROM knowledge_point p WHERE p.id=k.parent_id AND p.deleted=0 AND p.level=1
                   AND p.subject_id=k.subject_id)"""),
            'level1_with_parent': scalar(connection, """
                SELECT COUNT(*) FROM knowledge_point WHERE deleted=0 AND level=1 AND parent_id IS NOT NULL"""),
        }
    else:
        report['warnings'].append('knowledge_point 尚无 level 列：本次快照仍是迁移前结构')
    if 'knowledge_revision' in report['question_columns']:
        report['links'] = {
            'active': scalar(connection, 'SELECT COUNT(*) FROM question_knowledge_point WHERE deleted=0'),
            'classified_questions': scalar(connection, """
                SELECT COUNT(DISTINCT l.question_id) FROM question_knowledge_point l
                 JOIN question q ON q.id=l.question_id AND q.deleted=0 WHERE l.deleted=0"""),
            'unclassified_questions': scalar(connection, """
                SELECT COUNT(*) FROM question q WHERE q.deleted=0 AND NOT EXISTS(
                  SELECT 1 FROM question_knowledge_point l JOIN knowledge_point k
                    ON k.id=l.knowledge_point_id AND k.deleted=0 AND k.level=2
                   WHERE l.question_id=q.id AND l.deleted=0)"""),
            'multi_point_questions': scalar(connection, """
                SELECT COUNT(*) FROM (SELECT question_id FROM question_knowledge_point
                   WHERE deleted=0 GROUP BY question_id HAVING COUNT(*)>1)"""),
            'questions_without_primary': scalar(connection, """
                SELECT COUNT(*) FROM question q WHERE q.deleted=0 AND EXISTS(
                  SELECT 1 FROM question_knowledge_point l WHERE l.question_id=q.id AND l.deleted=0)
                 AND NOT EXISTS(SELECT 1 FROM question_knowledge_point l
                   WHERE l.question_id=q.id AND l.deleted=0 AND l.is_primary=1)"""),
            'questions_without_legacy_text': scalar(connection, """
                SELECT COUNT(*) FROM question WHERE deleted=0 AND knowledge_point IS NOT NULL
                 AND knowledge_point<>'' AND (legacy_knowledge_point IS NULL OR legacy_knowledge_point='')"""),
        }
    else:
        report['warnings'].append('question 尚无 knowledge_revision 列：本次快照仍是迁移前结构')
    report['runtime'] = {
        'taxonomy_version': (scalar(connection, "SELECT value FROM runtime_config WHERE name='taxonomy_version' AND deleted=0")
                             if table_exists(connection, 'runtime_config') else None),
        'data_revision': (scalar(connection, "SELECT value FROM runtime_config WHERE name='data_revision' AND deleted=0")
                          if table_exists(connection, 'runtime_config') else None),
        'write_guard': (scalar(connection, 'SELECT revision FROM write_guard WHERE id=1 AND deleted=0')
                        if table_exists(connection, 'write_guard') else None),
        'knowledge_assert': (scalar(connection, 'SELECT COUNT(*) FROM knowledge_assert WHERE id=1')
                             if table_exists(connection, 'knowledge_assert') else None),
    }
    if not table_exists(connection, 'write_guard'):
        report['warnings'].append('快照尚无 write_guard 表：需先应用运行时迁移')
    elif report['runtime']['write_guard'] is None:
        report['errors'].append('write_guard 守卫行缺失，禁止开始迁移')
    if report['duplicate_candidates']:
        report['errors'].append('存在同级同名目录行，需先人工合并')
    if arguments.seed:
        seed = load_json(arguments.seed)
        codes = [item.get('code') for item in seed.get('points', [])]
        report['seed'] = {'points': len(codes), 'duplicate_codes': sorted({code for code in codes if codes.count(code) > 1})}
        if report['seed']['duplicate_codes']:
            report['errors'].append('种子清单存在重复编码')
    output = arguments.out or str(ROOT / 'tmp' / ('knowledge-preflight-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S') + '.json'))
    path = write_json(output, report)
    print('预检完成：' + str(path))
    print('有效题目 %s，目录 %s，旧文本 %s 条' % (
        report['tables']['question'], report['tables']['knowledge_point'], len(report['legacy_texts'])))
    if report['errors']:
        print('错误：' + '；'.join(report['errors']))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
