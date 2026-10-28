"""备份数据库、上传文件和配置；只生成新目录，不修改业务数据。"""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def resolve_path(value):
    """按后端启动目录解析相对路径。"""
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (BACKEND_DIR / path).resolve()


def backup_database(settings, target, sqlite_path=None, pg_bin=None):
    """使用数据库原生备份机制生成快照，不复制运行中的 SQLite 主文件。"""
    db_type = settings.DB_TYPE.lower()
    if db_type == "sqlite":
        source = resolve_path(sqlite_path or settings.DB_PATH)
        if not source.is_file():
            raise RuntimeError("SQLite 数据库不存在，请检查 DB_PATH 或 --sqlite-path")
        output = target / "database.sqlite3"
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(output)) as dst:
                src.backup(dst)
                result = dst.execute("PRAGMA integrity_check").fetchall()
                if result != [("ok",)]:
                    raise RuntimeError("SQLite 备份完整性检查失败")
        return {"type": db_type, "source_path": str(source), "file": output.name}

    env = os.environ.copy()
    env['PGCONNECT_TIMEOUT'] = '15'
    if db_type == "mysql":
        executable = shutil.which("mysqldump")
        output = target / "database.sql"
        env["MYSQL_PWD"] = settings.DB_PASSWORD
        args = [executable, "--host", settings.DB_HOST, "--port", str(settings.DB_PORT),
                "--user", settings.DB_USER, "--single-transaction", "--quick",
                "--skip-lock-tables", "--hex-blob", "--default-character-set=utf8mb4",
                "--no-tablespaces", settings.DB_NAME]
    elif db_type in ("postgres", "postgresql"):
        executable = str(Path(pg_bin).resolve() / 'pg_dump.exe') if pg_bin and os.name == 'nt' else str(Path(pg_bin).resolve() / 'pg_dump') if pg_bin else shutil.which("pg_dump")
        output = target / "database.dump"
        env["PGPASSWORD"] = settings.DB_PASSWORD
        args = [executable, "--host", settings.DB_HOST, "--port", str(settings.DB_PORT),
                "--username", settings.DB_USER, "--no-password", "--format=custom", settings.DB_NAME]
    else:
        raise RuntimeError("不支持的 DB_TYPE")
    if executable is None or not Path(executable).is_file():
        raise RuntimeError("未找到数据库原生备份客户端，请先安装并加入 PATH")
    with output.open("wb") as stream:
        result = subprocess.run(args, stdout=stream, stderr=subprocess.PIPE, env=env, timeout=600)
    if result.returncode or output.stat().st_size == 0:
        # 客户端错误可能包含连接信息，不原样打印。
        raise RuntimeError("数据库原生备份失败，请检查客户端版本、连接和权限")
    return {"type": db_type, "database": settings.DB_NAME, "host": settings.DB_HOST,
            "port": settings.DB_PORT, "file": output.name}


def copy_optional(source, target, missing):
    """复制现存目录或文件，并记录缺失路径。"""
    if source.is_dir():
        shutil.copytree(source, target)
    elif source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    else:
        missing.append(str(source))


def file_hash(path):
    """分块计算 SHA-256，避免大文件占用过多内存。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_backup(directory):
    """核对清单中每个文件的大小和校验值。"""
    root = directory.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise RuntimeError("备份文件缺失或清单路径非法")
        if path.stat().st_size != item["size"] or file_hash(path) != item["sha256"]:
            raise RuntimeError("备份校验失败：" + item["path"])
    print(f"校验通过：{len(manifest['files'])} 个文件")


def main():
    """解析参数，执行备份或只读校验，失败时不生成成功清单。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(BACKEND_DIR.parent / "backups"))
    parser.add_argument("--sqlite-path", help="覆盖 SQLite 文件路径；相对路径按 backend 解析")
    parser.add_argument("--verify", type=Path, help="仅校验指定备份目录，无需连接数据库")
    parser.add_argument("--writers-paused", action="store_true", help="确认后端、Agent 和其他写入程序已暂停")
    parser.add_argument("--online-snapshot", action="store_true", help="PostgreSQL 在线一致性快照；上传文件仅尽力复制，不保证跨文件/数据库原子一致")
    parser.add_argument("--pg-bin", type=Path, help="PostgreSQL 客户端 bin 目录，无需修改全局 PATH")
    args = parser.parse_args()
    if args.verify:
        verify_backup(args.verify)
        return
    if not args.writers_paused and not args.online_snapshot:
        parser.error("请先暂停后端、Agent 及其他写入程序，再传入 --writers-paused，保证数据库与文件一致")

    args.output_dir = str(Path(args.output_dir).expanduser().resolve())
    if args.pg_bin:
        args.pg_bin = args.pg_bin.expanduser().resolve()

    # 与文档中的 backend 启动方式一致，使用同一配置类和环境变量优先级。
    os.chdir(BACKEND_DIR)
    from app.config import get_settings
    settings = get_settings()
    if args.online_snapshot and settings.DB_TYPE.lower() not in ('postgres', 'postgresql'):
        parser.error('--online-snapshot 当前仅支持 PostgreSQL')
    if args.sqlite_path and settings.DB_TYPE.lower() != "sqlite":
        parser.error("--sqlite-path 仅适用于 SQLite")
    uploads = resolve_path(settings.UPLOAD_DIR)
    sources = [BACKEND_DIR / "uploads", uploads, BACKEND_DIR / "config"]
    output_root = Path(args.output_dir).expanduser().resolve()
    if any(output_root.is_relative_to(source.resolve()) for source in sources):
        parser.error("备份目录不能位于上传或配置目录内部")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    target = output_root / ("easyfix_" + stamp)
    target.mkdir(parents=True, exist_ok=False)
    try:
        database = backup_database(settings, target, args.sqlite_path, args.pg_bin)
        missing = []
        copy_optional(BACKEND_DIR / "uploads", target / "uploads", missing)
        default_uploads = (BACKEND_DIR / "uploads").resolve()
        custom_upload = not uploads.is_relative_to(default_uploads)
        if custom_upload:
            copy_optional(uploads, target / "configured_uploads", missing)
        copy_optional(BACKEND_DIR / "config", target / "config", missing)
        copy_optional(BACKEND_DIR / ".env", target / "secrets" / "backend.env", missing)
        files = [{"path": p.relative_to(target).as_posix(), "size": p.stat().st_size,
                  "sha256": file_hash(p)} for p in sorted(target.rglob("*")) if p.is_file()]
        manifest = {"created_at_utc": stamp, "database": database,
                    "upload_source": str(uploads), "custom_upload_copy": custom_upload,
                    "missing_paths": missing, "files": files,
                    "contains_secrets": True, "writers_paused": args.writers_paused,
                    "consistency": 'writers_paused' if args.writers_paused else 'database_snapshot_files_best_effort'}
        (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        verify_backup(target)
        print(f"备份完成：{target}")
        if missing:
            print("部分可选目录不存在，详见 manifest.json 的 missing_paths；不会补回历史缺失图片。")
    except Exception:
        print(f"备份失败，目录不可用于恢复：{target}", file=sys.stderr)
        # 清单是成功标志；失败保留现场，不递归删除文件。
        (target / "manifest.json").unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"错误：{str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
