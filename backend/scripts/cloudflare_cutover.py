"""可回滚地冻结旧入口和 PostgreSQL 写入，完成后指向云端入口。"""

import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/'backend'
sys.path.insert(0,str(BACKEND))
MARKER=BACKEND/'config/cloudflare-cutover.json'
STATE=ROOT/'backups/cloudflare-cutover-state.json'
URL='https://easyfix-bl2.pages.dev'


def write_json(path,value):
    """原子替换控制文件，避免运行中的服务读取半个 JSON。"""
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)


def main():
    """只操作当前配置对应的数据库，保留切换前的只读设置供回滚。"""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','freeze','complete','rollback'])
    args=parser.parse_args();os.chdir(BACKEND)
    from app.config import get_settings
    import psycopg2
    from psycopg2 import sql
    settings=get_settings()
    if settings.DB_TYPE not in ('postgres','postgresql'):raise RuntimeError('当前切换脚本仅支持已验证的 PostgreSQL 源')
    connection=psycopg2.connect(host=settings.DB_HOST,port=settings.DB_PORT,user=settings.DB_USER,password=settings.DB_PASSWORD,dbname=settings.DB_NAME,connect_timeout=15,options='-c default_transaction_read_only=off')
    connection.autocommit=True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT setting FROM pg_db_role_setting r CROSS JOIN LATERAL unnest(r.setconfig) setting WHERE r.setdatabase=(SELECT oid FROM pg_database WHERE datname=%s) AND r.setrole=0 AND setting LIKE 'default_transaction_read_only=%%'",(settings.DB_NAME,))
            configured=cursor.fetchone();previous=configured[0].split('=',1)[1] if configured else None
            if args.action=='status':
                print(json.dumps({'database':settings.DB_NAME,'database_read_only_default':previous,'marker':json.loads(MARKER.read_text(encoding='utf-8')) if MARKER.exists() else None}));return
            if args.action=='freeze':
                if STATE.exists() and MARKER.exists():raise RuntimeError('已存在切换状态，请先核对状态，禁止覆盖原恢复点')
                state={'database':settings.DB_NAME,'host':settings.DB_HOST,'port':settings.DB_PORT,'previous_read_only':previous,'cloud_url':URL,'started_at_utc':datetime.now(timezone.utc).isoformat()}
                write_json(STATE,state)
                write_json(MARKER,{'state':'freeze','cloud_url':URL})
                cursor.execute(sql.SQL('ALTER DATABASE {} SET default_transaction_read_only=on').format(sql.Identifier(settings.DB_NAME)))
                cursor.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid() AND backend_type=\'client backend\'',(settings.DB_NAME,))
                terminated=sum(bool(row[0]) for row in cursor.fetchall())
                print(json.dumps({'frozen':True,'database':settings.DB_NAME,'closed_source_connections':terminated}))
            elif args.action=='complete':
                if not STATE.exists() or not MARKER.exists():raise RuntimeError('尚未冻结源数据，不能宣布切换完成')
                state=json.loads(STATE.read_text(encoding='utf-8'))
                state['completed_at_utc']=datetime.now(timezone.utc).isoformat()
                write_json(STATE,state);write_json(MARKER,{'state':'complete','cloud_url':URL})
                print(json.dumps({'cutover_complete':True,'cloud_url':URL,'source_remains_read_only':True}))
            else:
                if not STATE.exists():raise RuntimeError('不存在恢复点，禁止猜测数据库原设置')
                state=json.loads(STATE.read_text(encoding='utf-8'))
                if (state['database'],state['host'],state['port'])!=(settings.DB_NAME,settings.DB_HOST,settings.DB_PORT):raise RuntimeError('当前数据库与恢复点不一致')
                if state['previous_read_only'] is None:
                    cursor.execute(sql.SQL('ALTER DATABASE {} RESET default_transaction_read_only').format(sql.Identifier(settings.DB_NAME)))
                else:
                    cursor.execute(sql.SQL('ALTER DATABASE {} SET default_transaction_read_only={}').format(sql.Identifier(settings.DB_NAME),sql.Literal(state['previous_read_only'])))
                cursor.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid() AND backend_type=\'client backend\'',(settings.DB_NAME,))
                if MARKER.exists():MARKER.rename(MARKER.with_name('cloudflare-cutover.rolled-back.json'))
                print(json.dumps({'source_unfrozen':True,'warning':'Rollback does not copy new cloud writes back to the source.'}))
    finally:connection.close()


if __name__=='__main__':main()
