"""从 starmap_seed/ 下的三个 JSON 生成迁移 0013（知识星空的种子数据）。

- english_grammar.json：英语语法新体系（按课程标准整理，二级考点带"大约几年级学"）
- math_sections.json：沪教版六年级上册数学的节，以及每节对应的二级考点编号
- links.json：先学后学连线（考点编号对）

生成的 SQL 只用 INSERT ... SELECT ... WHERE NOT EXISTS，可以重复执行；考点编号在执行时按 code 查，不写死 id。
运行：python cloudflare/scripts/build_starmap_seed.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from knowledge_model import normalize_name_key  # noqa: E402

SEED_DIR = ROOT / 'scripts' / 'starmap_seed'
CATALOG_FILE = ROOT / 'scripts' / 'knowledge_grade6_catalog.json'
OUTPUT = ROOT / 'migrations' / '0013_starmap_seed.sql'
TEXTBOOK = '沪教版（五四制，2024）六年级上册'


def load_inputs():
    """读取三个种子 JSON，返回 (英语考点, 数学的节, 连线)。"""
    def read(name):
        """读取一个 JSON 文件。"""
        return json.loads((SEED_DIR / name).read_text(encoding='utf-8'))
    return read('english_grammar.json'), read('math_sections.json'), read('links.json')


def quote(value):
    """把 Python 值写成 SQL 字面量（文字里的单引号写成两个）。"""
    if value is None:
        return 'NULL'
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def known_codes(english):
    """所有可以被引用的考点编号：正式目录里的数学考点 + 新的英语考点。"""
    catalog = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))['points']
    return {item['code'] for item in catalog if item['subject'] == '数学'} | {item['code'] for item in english}


def check_codes(codes, known):
    """有不存在的考点编号时报错，指出是哪些。"""
    missing = sorted(set(codes) - known)
    if missing:
        raise ValueError('种子数据引用了不存在的考点编号：' + '、'.join(missing))


def point_sql(item):
    """插入一个英语考点（已存在同 code 的未删除考点时跳过）。"""
    parent = ('(SELECT id FROM knowledge_point WHERE code=%s AND deleted=0)' % quote(item['parent_code'])
              if item['level'] == 2 else 'NULL')
    return ('INSERT INTO knowledge_point(code,name,name_key,level,parent_id,subject_id,grade,learn_grade,sort_order,'
            'deleted,created_at,updated_at)\n  SELECT %s,%s,%s,%d,%s,(SELECT id FROM subject WHERE name=\'英语\' AND '
            'deleted=0),NULL,%s,%d,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP\n  WHERE NOT EXISTS (SELECT 1 FROM '
            'knowledge_point WHERE code=%s AND deleted=0);'
            % (quote(item['code']), quote(item['name']), quote(normalize_name_key(item['name'])), item['level'],
               parent, quote(item.get('learn_grade')), item['sort_order'], quote(item['code'])))


def section_sql(section):
    """插入教材的一节，以及它对应的考点。"""
    lines = [('INSERT INTO textbook_section(student_id,subject_id,textbook,chapter_no,chapter_name,section_no,'
              'section_name,sort_order,deleted,created_at)\n  SELECT 1,(SELECT id FROM subject WHERE name=\'数学\' AND '
              'deleted=0),%s,%d,%s,%s,%s,%d,0,CURRENT_TIMESTAMP\n  WHERE NOT EXISTS (SELECT 1 FROM textbook_section '
              'WHERE textbook=%s AND section_no=%s AND deleted=0);'
              % (quote(TEXTBOOK), section['chapter_no'], quote(section['chapter_name']), quote(section['section_no']),
                 quote(section['section_name']), section['sort_order'], quote(TEXTBOOK), quote(section['section_no'])))]
    for code in section['point_codes']:
        lines.append(('INSERT INTO textbook_section_point(section_id,knowledge_point_id,deleted,created_at)\n'
                      '  SELECT s.id,k.id,0,CURRENT_TIMESTAMP FROM textbook_section s, knowledge_point k\n'
                      '  WHERE s.textbook=%s AND s.section_no=%s AND s.deleted=0 AND k.code=%s AND k.deleted=0\n'
                      '    AND NOT EXISTS (SELECT 1 FROM textbook_section_point x WHERE x.section_id=s.id AND '
                      'x.knowledge_point_id=k.id AND x.deleted=0);')
                     % (quote(TEXTBOOK), quote(section['section_no']), quote(code)))
    return '\n'.join(lines)


def link_sql(link):
    """插入一条先学后学连线。"""
    return ('INSERT INTO knowledge_link(from_point_id,to_point_id,deleted,created_at)\n'
            '  SELECT a.id,b.id,0,CURRENT_TIMESTAMP FROM knowledge_point a, knowledge_point b\n'
            '  WHERE a.code=%s AND a.deleted=0 AND b.code=%s AND b.deleted=0\n'
            '    AND NOT EXISTS (SELECT 1 FROM knowledge_link x WHERE x.from_point_id=a.id AND x.to_point_id=b.id '
            'AND x.deleted=0);' % (quote(link['from']), quote(link['to'])))


def build_sql(english, sections, links):
    """拼出完整的 0013 文件内容；引用了不存在的考点编号时抛 ValueError。"""
    known = known_codes(english)
    check_codes([item['parent_code'] for item in english if item['level'] == 2], known)
    check_codes([code for section in sections for code in section['point_codes']], known)
    check_codes([code for link in links for code in (link['from'], link['to'])], known)
    parts = ['-- 0013：知识星空的种子数据。由 cloudflare/scripts/build_starmap_seed.py 生成，不要手改。',
             '-- 全部语句可以重复执行（已存在的跳过）。', '',
             '-- 1. 英语语法新体系（一级在前）']
    parts += [point_sql(item) for item in sorted(english, key=lambda item: item['level'])]
    parts += ['', '-- 2. 数学教材的节与考点对应（%s）' % TEXTBOOK]
    parts += [section_sql(section) for section in sections]
    parts += ['', '-- 3. 先学后学连线']
    parts += [link_sql(link) for link in links]
    parts += ['', '-- 4. 考点目录有变化，统计缓存随之失效',
              "UPDATE runtime_config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE name='taxonomy_version' "
              'AND deleted=0;',
              "UPDATE runtime_config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE name='data_revision' "
              'AND deleted=0;', '']
    return '\n'.join(parts)


def main():
    """生成 0013 并打印条数。"""
    english, sections, links = load_inputs()
    OUTPUT.write_text(build_sql(english, sections, links), encoding='utf-8', newline='\n')
    print('已生成 %s：英语考点 %d 个，节 %d 个，连线 %d 条' % (OUTPUT.name, len(english), len(sections), len(links)))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
