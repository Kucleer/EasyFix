"""知识点迁移工具共用的只读辅助函数。

所有脚本默认只读取已导出的 D1 SQLite 快照或已审核 JSON，不直接连接生产库。
"""

import json
import pathlib
import sqlite3


def connect(path):
    """以只读方式打开导出的 D1 SQLite 快照。"""
    target = pathlib.Path(path)
    if not target.exists():
        raise SystemExit('快照不存在：' + str(target))
    connection = sqlite3.connect('file:' + target.as_posix() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def columns(connection, table):
    """读取表的列名。"""
    return [row['name'] for row in connection.execute('PRAGMA table_info(' + table + ')')]


def inventory(connection, table):
    """读取表相关的索引、触发器与视图定义。"""
    rows = connection.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger','view') ORDER BY type,name",
        (table,))
    return [{'type': row['type'], 'name': row['name'], 'sql': row['sql']} for row in rows]


def require_columns(connection, table, expected):
    """确认迁移所需列存在，缺失时给出明确提示。"""
    present = set(columns(connection, table))
    missing = [name for name in expected if name not in present]
    if missing:
        raise SystemExit('表 ' + table + ' 缺少列：' + ', '.join(missing) + '；请先应用 0009 迁移')


def table_exists(connection, table):
    """判断快照中是否存在指定表。"""
    row = connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row and row[0])


def scalar(connection, sql, parameters=()):
    """返回单值查询结果。"""
    row = connection.execute(sql, parameters).fetchone()
    return row[0] if row is not None else None


def rows(connection, sql, parameters=()):
    """返回字典列表。"""
    return [dict(row) for row in connection.execute(sql, parameters).fetchall()]


def load_json(path):
    """读取 UTF-8 JSON 文件。"""
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    """写入私有 tmp/backups 目录，不自动提交到仓库。"""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    return target


def write_text(path, text):
    """写出生成的 SQL。"""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8', newline='\n')
    return target
