"""根据已核对的 SQLite 快照生成保留历史记录的 D1 最终同步 SQL。"""

import argparse
import json
from pathlib import Path
import sqlite3


def identifier(value):
    """引用来自数据库结构的标识符。"""
    return '"'+value.replace('"','""')+'"'


def main():
    """软删除目标旧快照并逐主键恢复源数据，不删除任何历史记录。"""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot',type=Path)
    args=parser.parse_args()
    connection=sqlite3.connect(args.snapshot/'database.sqlite3')
    tables=[row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    statements=['PRAGMA defer_foreign_keys=ON;']
    for table in tables:
        statements.append('UPDATE '+identifier(table)+' SET deleted=1;')
    counts={}
    for table in tables:
        schema=connection.execute('PRAGMA table_info('+identifier(table)+')').fetchall()
        columns=[row[1] for row in schema]
        primary=[row[1] for row in sorted(schema,key=lambda row:row[5]) if row[5]]
        if not primary:raise RuntimeError('缺少主键：'+table)
        rows=connection.execute('SELECT '+','.join(map(identifier,columns))+' FROM '+identifier(table)).fetchall()
        counts[table]=len(rows)
        target_columns=columns if 'deleted' in columns else columns+['deleted']
        prefix='INSERT INTO '+identifier(table)+'('+','.join(map(identifier,target_columns))+') VALUES('
        suffix=') ON CONFLICT('+','.join(map(identifier,primary))+') DO UPDATE SET '+','.join(identifier(column)+'=excluded.'+identifier(column) for column in target_columns if column not in primary)+';'
        for row in rows:
            values=list(row) if 'deleted' in columns else [*row,0]
            literals=[connection.execute('SELECT quote(?)',(value,)).fetchone()[0] for value in values]
            statements.append(prefix+','.join(literals)+suffix)
    statements.append("UPDATE runtime_config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT),updated_at=datetime('now') WHERE name='data_revision';")
    output=args.snapshot/'sync.sql'
    output.write_text('\n'.join(statements)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'sql':str(output),'tables':counts,'hard_deletes':0}))


if __name__=='__main__':main()
