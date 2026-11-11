"""英语错题重新打标：把旧的英语考点关联换成按课程标准整理的新语法考点（EG- 开头）。

输入映射文件（放在被忽略的 tmp/ 下，不提交）：
    [{"question_id": 123, "point_codes": ["EG-TEN-03"], "primary_code": "EG-TEN-03"},
     {"question_id": 124, "point_codes": [], "primary_code": null}]      # 空列表 = 词汇类，不进语法星空
输出一个 SQL 文件，所有语句重复执行结果不变（版本号除外）：
    1. 每道映射里的题：软删除不在新列表里的关联，补上新关联，设置主考点，更新旧的考点文字字段；
    2. 软删除旧英语考点（E6- 开头，先二级后一级）；映射漏了还挂着旧考点的题时，数据库会报错停下；
    3. 递增考点目录版本和数据版本。
运行：python cloudflare/scripts/starmap_retag.py tmp/starmap/retag.json tmp/starmap/retag.sql
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRAMMAR_FILE = ROOT / 'scripts' / 'starmap_seed' / 'english_grammar.json'
OLD_PREFIX = 'E6-'


def quote(value):
    """把值写成 SQL 字面量。"""
    if value is None:
        return 'NULL'
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def new_point_codes():
    """英语新体系里的二级考点编号。"""
    return {item['code'] for item in json.loads(GRAMMAR_FILE.read_text(encoding='utf-8')) if item['level'] == 2}


def check_mapping(mapping):
    """检查映射：编号必须是英语新体系的二级考点；有考点时主考点必须在其中；没有考点时主考点为空。"""
    known = new_point_codes()
    for entry in mapping:
        codes, primary = entry.get('point_codes') or [], entry.get('primary_code')
        if not isinstance(entry.get('question_id'), int):
            raise ValueError('question_id 必须是整数：%r' % entry)
        unknown = [code for code in codes if code not in known]
        if unknown:
            raise ValueError('第 %d 题用了不在英语新体系里的编号：%s' % (entry['question_id'], '、'.join(unknown)))
        if codes and primary not in codes:
            raise ValueError('第 %d 题的主考点不在它的考点列表里' % entry['question_id'])
        if not codes and primary is not None:
            raise ValueError('第 %d 题没有考点，主考点应为空' % entry['question_id'])


ENGLISH = "(SELECT id FROM subject WHERE name='英语' AND deleted=0)"


def question_sql(entry):
    """一道题的重新打标语句。每条语句都只作用于英语题（数学题混进映射也不会被改动）。

    写法沿用 knowledge.link_statements：先清掉主考点标记，再软删除不要的关联，
    已有的关联用 ON CONFLICT 恢复（关联表的 (题, 考点) 唯一，含已删除的行），最后单独设主考点。
    """
    qid, codes, primary = entry['question_id'], entry.get('point_codes') or [], entry.get('primary_code')
    code_list = ','.join(quote(code) for code in codes) or "''"
    english = 'EXISTS (SELECT 1 FROM question q WHERE q.id=%d AND q.deleted=0 AND q.subject_id=%s)' % (qid, ENGLISH)
    lines = [
        'UPDATE question_knowledge_point SET is_primary=0,updated_at=CURRENT_TIMESTAMP '
        'WHERE question_id=%d AND is_primary=1 AND %s;' % (qid, english),
        'UPDATE question_knowledge_point SET deleted=1,updated_at=CURRENT_TIMESTAMP WHERE question_id=%d AND deleted=0 '
        'AND knowledge_point_id NOT IN (SELECT id FROM knowledge_point WHERE deleted=0 AND code IN (%s)) AND %s;'
        % (qid, code_list, english)]
    for code in codes:
        lines.append(
            "INSERT INTO question_knowledge_point(question_id,knowledge_point_id,is_primary,source,deleted,created_at,"
            "updated_at) SELECT %d,k.id,0,'retag',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM knowledge_point k "
            'WHERE k.code=%s AND k.deleted=0 AND %s '
            'ON CONFLICT(question_id,knowledge_point_id) DO UPDATE SET deleted=0,is_primary=0,'
            'updated_at=excluded.updated_at;' % (qid, quote(code), english))
    if primary:
        lines.append('UPDATE question_knowledge_point SET is_primary=1,updated_at=CURRENT_TIMESTAMP WHERE question_id=%d '
                     'AND deleted=0 AND knowledge_point_id=(SELECT id FROM knowledge_point WHERE code=%s AND deleted=0) '
                     'AND %s;' % (qid, quote(primary), english))
    name = ('(SELECT name FROM knowledge_point WHERE code=%s AND deleted=0)' % quote(primary)) if primary else 'NULL'
    lines.append('UPDATE question SET knowledge_point=%s,knowledge_revision=COALESCE(knowledge_revision,0)+1 '
                 'WHERE id=%d AND deleted=0 AND subject_id=%s;' % (name, qid, ENGLISH))
    return '\n'.join(lines)


def build_retag_sql(mapping):
    """生成完整的重新打标 SQL；映射不合格时抛 ValueError。

    不会替映射漏掉的题删除旧关联：只要还有未删除的英语题挂着旧考点，
    软删除旧考点那一步会被数据库触发器（KP_INUSE）拒绝，整件事停下来，而不是悄悄丢掉考点。
    """
    check_mapping(mapping)
    parts = ['-- 英语错题重新打标，由 cloudflare/scripts/starmap_retag.py 生成。', '']
    parts += [question_sql(entry) for entry in mapping]
    parts += ['', '-- 旧英语考点：先二级后一级软删除；还有题挂着旧考点时触发器会报错停下',
              "UPDATE knowledge_point SET deleted=1,updated_at=CURRENT_TIMESTAMP WHERE code LIKE '%s%%' AND level=2 "
              'AND deleted=0;' % OLD_PREFIX,
              "UPDATE knowledge_point SET deleted=1,updated_at=CURRENT_TIMESTAMP WHERE code LIKE '%s%%' AND level=1 "
              'AND deleted=0;' % OLD_PREFIX,
              "UPDATE runtime_config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE name IN "
              "('taxonomy_version','data_revision') AND deleted=0;", '']
    return '\n'.join(parts)


def main(argv):
    """读取映射文件，写出 SQL 文件。"""
    source, target = pathlib.Path(argv[0]), pathlib.Path(argv[1])
    mapping = json.loads(source.read_text(encoding='utf-8'))
    target.write_text(build_retag_sql(mapping), encoding='utf-8', newline='\n')
    print('已生成 %s：%d 道题' % (target, len(mapping)))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1:])
