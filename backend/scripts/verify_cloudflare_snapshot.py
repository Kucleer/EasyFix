"""将 D1 完整导出回读，逐主键逐字段核对源快照和软删除额外记录。"""

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
from sync_cloudflare_d1 import identifier


def main():
    """以实际远端导出为依据验证，而非只比较表数量。"""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot',type=Path)
    args=parser.parse_args();source=sqlite3.connect(args.snapshot/'database.sqlite3')
    remote=sqlite3.connect(':memory:')
    remote.executescript((args.snapshot/'remote.sql').read_text(encoding='utf-8'))
    if remote.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise RuntimeError('远端导出完整性错误')
    if remote.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('远端外键核对失败')
    tables=[row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    report={}
    for table in tables:
        schema=source.execute('PRAGMA table_info('+identifier(table)+')').fetchall()
        columns=[row[1] for row in schema];primary=[row[1] for row in sorted(schema,key=lambda row:row[5]) if row[5]]
        select='SELECT '+','.join(map(identifier,columns))+' FROM '+identifier(table)
        positions=[columns.index(key) for key in primary]
        def key(row):return tuple(row[index] for index in positions)
        original={key(row):row for row in source.execute(select)}
        restored={key(row):row for row in remote.execute(select)}
        differences=[(pk,columns[index]) for pk,row in original.items() if pk in restored for index,value in enumerate(row) if restored[pk][index]!=value]
        if differences:raise RuntimeError('字段内容不一致：'+table+' '+repr(differences[:3]))
        if any(pk not in restored for pk in original):raise RuntimeError('缺少记录：'+table)
        active=remote.execute('SELECT '+','.join(map(identifier,primary))+' FROM '+identifier(table)+' WHERE deleted=0').fetchall()
        if any(pk not in original for pk in active):raise RuntimeError('额外记录仍未软删除：'+table)
        expected=source.execute('SELECT COUNT(*) FROM '+identifier(table)+(' WHERE deleted=0' if 'deleted' in columns else '')).fetchone()[0]
        if len(active)!=expected:raise RuntimeError('有效记录数量不一致：'+table)
        report[table]={'source_rows':len(original),'active_rows':len(active),'soft_deleted_extra_rows':len(restored)-len(original),'all_source_fields_equal':True}
    output={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'integrity_check':'ok','foreign_key_check':'ok','tables':report}
    (args.snapshot/'final-verification.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps({'tables_verified':len(report),'source_rows_verified':sum(item['source_rows'] for item in report.values()),'all_source_fields_equal':True,'active_counts_equal':True,'extra_rows_all_soft_deleted':True}))


if __name__=='__main__':main()
