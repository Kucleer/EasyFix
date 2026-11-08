"""按盘点清单上传图片至私有 R2 桶，记录每项结果，支持断点续传。"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import mimetypes
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    """校验清单中的本地文件后上传，已成功的相同文件跳过。"""
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    progress_file = ROOT / 'backups' / 'cloudflare-r2-image-progress.json'
    progress = json.loads(progress_file.read_text(encoding='utf-8')) if progress_file.exists() else {}
    def upload(item):
        """上传单个文件，失败时保留错误供重试。"""
        path = Path(manifest['upload_source']) / item['key']
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != item['sha256']:
            return item['key'], {'success': False, 'reason': 'source_changed'}
        if progress.get(item['key'], {}).get('sha256') == digest:
            return item['key'], progress[item['key']]
        result = subprocess.run(['node', str(ROOT / 'tmp/cloudflare-cli.cjs'), 'r2', 'object', 'put',
                                 'easyfix/' + item['key'], '--file', str(path), '--remote',
                                 '--content-type', mimetypes.guess_type(path)[0] or 'application/octet-stream'],
                                capture_output=True, timeout=180, cwd=ROOT)
        return item['key'], {'success': result.returncode == 0, 'sha256': digest if result.returncode == 0 else None,
                             'size': item['size']}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(upload, item) for item in manifest['files']]):
            key, result = future.result()
            progress[key] = result
            progress_file.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'done': len(progress), 'total': len(manifest['files']), 'success': result['success']}), flush=True)
    failed = sum(not item['success'] for item in progress.values())
    print(json.dumps({'uploaded': len(progress) - failed, 'failed': failed}), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
