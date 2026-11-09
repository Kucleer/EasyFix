"""保留但移出已弃用的生成版 ORM 分析副本，减少 Worker 打包体积。"""

from datetime import datetime,timezone
from pathlib import Path
import shutil


def main():
    """验证绝对路径位于工作区，再将生成目录归档到备份目录。"""
    root=Path(__file__).resolve().parents[2]
    source=(root/'cloudflare/src/legacy').resolve()
    target=(root/'backups'/('cloudflare_unused_analytics_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))).resolve()
    if not source.is_relative_to(root) or not target.is_relative_to(root/'backups'):raise RuntimeError('归档路径越界')
    if source.exists():shutil.move(str(source),str(target))
    print('Archived unused generated analytics package; source preserved in backups.')


if __name__=='__main__':main()
