"""只读盘点当前数据库与上传文件，生成迁移清单，不输出密钥。"""

import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def main():
    """在只读事务中统计实际数据库，并记录附件校验值。"""
    os.chdir(BACKEND)
    from app.config import get_settings
    import psycopg2
    from psycopg2 import sql
    settings = get_settings()
    if settings.DB_TYPE not in ('postgres', 'postgresql'):
        raise RuntimeError('当前盘点脚本仅支持 PostgreSQL，禁止自动选择旧 SQLite 文件')
    connection = psycopg2.connect(host=settings.DB_HOST, port=settings.DB_PORT,
                                 dbname=settings.DB_NAME, user=settings.DB_USER,
                                 password=settings.DB_PASSWORD, connect_timeout=15)
    connection.set_session(readonly=True, isolation_level='REPEATABLE READ')
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name")
            tables = [row[0] for row in cursor.fetchall()]
            counts = {}
            for table in tables:
                cursor.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table)))
                counts[table] = cursor.fetchone()[0]
            cursor.execute("SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position")
            columns = [dict(zip(('table', 'column', 'type', 'nullable', 'default'), row)) for row in cursor.fetchall()]
    finally:
        connection.close()
    uploads = Path(settings.UPLOAD_DIR).resolve()
    files = []
    for path in sorted(uploads.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            files.append({'key': path.relative_to(uploads).as_posix(), 'size': path.stat().st_size,
                          'sha256': digest})
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'database_type': settings.DB_TYPE,
              'database_name': settings.DB_NAME, 'tables': counts, 'columns': columns,
              'upload_source': str(uploads), 'files': files, 'upload_bytes': sum(f['size'] for f in files)}
    output = BACKEND.parent / 'backups' / ('cloudflare_inventory_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(output), 'tables': counts, 'image_files': len(files), 'upload_bytes': report['upload_bytes']}, ensure_ascii=True))


if __name__ == '__main__':
    main()
