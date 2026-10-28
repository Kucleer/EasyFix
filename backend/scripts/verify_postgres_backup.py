"""把备份恢复到唯一临时 PostgreSQL 库验证，再移除该临时库；不覆盖业务库。"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / 'scripts'))


def main():
    """校验备份，创建隔离库，完整恢复并检查表和记录。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-dir', required=True, type=Path)
    parser.add_argument('--pg-bin', required=True, type=Path)
    args = parser.parse_args()
    directory = args.backup_dir.resolve()
    client = args.pg_bin.resolve() / ('pg_restore.exe' if os.name == 'nt' else 'pg_restore')
    from backup_data import verify_backup
    verify_backup(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    os.chdir(BACKEND)
    from app.config import get_settings
    import psycopg2
    from psycopg2 import sql
    settings = get_settings()
    if settings.DB_TYPE not in ('postgres', 'postgresql') or manifest['database'].get('database') != settings.DB_NAME:
        raise RuntimeError('备份与当前 PostgreSQL 数据库不匹配')
    name = 'easyfix_restore_check_' + uuid.uuid4().hex[:12]
    assert name != settings.DB_NAME
    connection_args = dict(host=settings.DB_HOST, port=settings.DB_PORT, user=settings.DB_USER,
                           password=settings.DB_PASSWORD, connect_timeout=15)
    connection = psycopg2.connect(dbname=settings.DB_NAME, **connection_args)
    connection.autocommit = True
    created = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(name)))
            created = True
        env = os.environ.copy()
        env.update(PGPASSWORD=settings.DB_PASSWORD, PGCONNECT_TIMEOUT='15')
        result = subprocess.run([str(client), '--host', settings.DB_HOST, '--port', str(settings.DB_PORT),
                                 '--username', settings.DB_USER, '--no-password', '--no-owner', '--no-privileges',
                                 '--exit-on-error', '--dbname', name, str(directory / manifest['database']['file'])],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
        if result.returncode:
            raise RuntimeError('隔离库恢复失败，原业务库未改动')
        restored = psycopg2.connect(dbname=name, **connection_args)
        try:
            restored.set_session(readonly=True, autocommit=True)
            with restored.cursor() as cursor:
                cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
                tables = [row[0] for row in cursor.fetchall()]
                counts = {}
                for table in ['question', 'practice_set', 'subject']:
                    cursor.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table)))
                    counts[table] = cursor.fetchone()[0]
                cursor.execute("SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT i.indisvalid")
                if cursor.fetchone()[0]:
                    raise RuntimeError('恢复后存在无效索引')
            report = {'restore_passed': True, 'table_count': len(tables), 'row_counts': counts,
                      'temporary_database': name, 'production_database_unchanged': True}
        finally:
            restored.close()
    finally:
        try:
            if created:
                with connection.cursor() as cursor:
                    cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
        finally:
            connection.close()
    report['temporary_database_removed'] = True
    (directory / 'restore-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
