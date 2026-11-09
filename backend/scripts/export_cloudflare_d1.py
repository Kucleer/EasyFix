"""只读导出 PostgreSQL 到隔离 SQLite，保留结构和数据并生成 D1 SQL。"""

import datetime
import decimal
import json
import os
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def main():
    """在一致性只读事务内复制数据，回读逐行核对后生成导入文件。"""
    os.chdir(BACKEND)
    from app.config import get_settings
    from sqlalchemy import create_engine, MetaData, Table, Column, text
    from sqlalchemy.schema import ForeignKeyConstraint, UniqueConstraint, CheckConstraint
    settings = get_settings()
    if settings.DB_TYPE not in ('postgres', 'postgresql'):
        raise RuntimeError('仅允许当前 PostgreSQL 数据源')
    target = BACKEND.parent / 'backups' / ('cloudflare_d1_' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    target.mkdir(parents=True, exist_ok=False)
    source = create_engine(settings.DATABASE_URL)
    destination = create_engine('sqlite:///' + (target / 'database.sqlite3').as_posix())
    counts = {}
    with source.connect().execution_options(isolation_level='REPEATABLE READ') as src:
        with src.begin():
            src.execute(text('SET TRANSACTION READ ONLY'))
            original = MetaData()
            original.reflect(bind=src)
            converted = MetaData()
            for table in original.sorted_tables:
                clone = table.to_metadata(converted)
                for column in clone.columns:
                    column.server_default = None
                    if column.identity is not None:
                        column.identity = None
            converted.create_all(destination)
            with destination.begin() as dst:
                for table in original.sorted_tables:
                    clone = converted.tables[table.name]
                    rows = [dict(row) for row in src.execute(table.select().order_by(*table.primary_key.columns)).mappings()]
                    for offset in range(0, len(rows), 100):
                        dst.execute(clone.insert(), rows[offset:offset + 100])
                    restored = [dict(row) for row in dst.execute(clone.select().order_by(*clone.primary_key.columns)).mappings()]
                    if rows != restored:
                        raise RuntimeError('回读不一致：' + table.name)
                    counts[table.name] = len(rows)
    destination.dispose()
    source.dispose()
    import sqlite3
    with sqlite3.connect(target / 'database.sqlite3') as connection:
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('SQLite 完整性检查失败')
        if connection.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('存在外键孤立记录，禁止自动修复或导入')
        schemas = [row[0] + ';' for row in connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name") if row[0]]
        inserts = [line for line in connection.iterdump() if line.startswith('INSERT INTO')]
        order = {table.name: index for index, table in enumerate(original.sorted_tables)}
        inserts.sort(key=lambda line: order[line.split('"', 2)[1]])
        indexes = [row[0] + ';' for row in connection.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name")]
        dump = '\n'.join(schemas + inserts + indexes)
        (target / 'import.sql').write_text('PRAGMA defer_foreign_keys=ON;\n' + dump + '\n', encoding='utf-8', newline='\n')
    (target / 'manifest.json').write_text(json.dumps({'source': 'postgresql', 'tables': counts, 'roundtrip_verified': True}, indent=2), encoding='utf-8')
    print(json.dumps({'directory': str(target), 'tables': counts}, ensure_ascii=True))


if __name__ == '__main__':
    main()
