"""把正式库的表结构整理成一份只含结构的 SQL 文件，供测试建库使用。

输入是 Wrangler 只读查询的 JSON 输出，不含任何业务数据。查询语句：

    SELECT type,name,tbl_name,sql FROM sqlite_master
    WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
      AND name NOT LIKE '_cf_%' AND name NOT LIKE 'd1_%'

用法：python cloudflare/scripts/extract_schema.py <查询结果.json> <输出.sql>
"""
import json
import sqlite3
import sys
from pathlib import Path

# 建立顺序：先表，再索引，最后触发器（触发器和索引都依赖表已存在）
TYPE_ORDER = {'table': 0, 'index': 1, 'trigger': 2}


def load_rows(path):
    """读取 Wrangler 的 JSON 输出，返回 sqlite_master 的行列表。"""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    # Wrangler 输出是一个数组，每条语句一项，行在 results 里
    return data[0]['results']


def build_schema(rows):
    """按“表 → 索引 → 触发器”的顺序拼出建立语句，每条以分号结尾。"""
    kept = [row for row in rows if row.get('sql') and row['type'] in TYPE_ORDER]
    kept.sort(key=lambda row: (TYPE_ORDER[row['type']], row['name']))
    return ''.join(row['sql'].rstrip().rstrip(';') + ';\n' for row in kept)


def check_schema(schema):
    """在内存库里执行一遍，确认这份结构能独立建库，返回表的数量。"""
    connection = sqlite3.connect(':memory:')
    connection.executescript(schema)
    count = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    connection.close()
    return count


def main(argv):
    """读取查询结果，写出结构文件，并打印表的数量。"""
    if len(argv) != 3:
        print(__doc__)
        return 1
    schema = build_schema(load_rows(argv[1]))
    tables = check_schema(schema)
    header = '-- 迁移 0011 之前的正式库结构（只含结构，不含数据），由 extract_schema.py 生成。\n'
    Path(argv[2]).write_text(header + schema, encoding='utf-8', newline='\n')
    print(f'tables: {tables}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
