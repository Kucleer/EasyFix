"""根据清单上传全部附件，保留校验值与断点进度，不公开存储桶。"""

from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    """仅上传尚未完成的相同内容，避免重复消耗 R2 写入。"""
    root=Path(__file__).resolve().parents[2]
    manifest=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    progress_file=root/'backups/cloudflare-r2-file-progress.json'
    progress=json.loads(progress_file.read_text(encoding='utf-8')) if progress_file.exists() else {}
    old=root/'backups/cloudflare-r2-image-progress.json'
    if old.exists():
        for key,item in json.loads(old.read_text(encoding='utf-8')).items():
            if item.get('success'):progress.setdefault(key,item)
    pending=[item for item in manifest['files'] if not(progress.get(item['key'],{}).get('success') and progress[item['key']].get('sha256')==item['sha256'])]
    def upload(item):
        """上传前复核文件，失败重试一次，保持远程路径不变。"""
        path=Path(item['path'])
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=item['sha256']:return item['key'],{'success':False,'reason':'source_changed'}
        for attempt in range(2):
            result=subprocess.run(['node',str(root/'tmp/cloudflare-cli.cjs'),'r2','object','put','easyfix/'+item['key'],'--file',str(path),'--remote','--content-type',item['content_type']],cwd=root,capture_output=True,timeout=180)
            if result.returncode==0:break
        return item['key'],{'success':result.returncode==0,'sha256':digest if result.returncode==0 else None,'size':item['size']}
    print(json.dumps({'already_uploaded':len(manifest['files'])-len(pending),'pending':len(pending)}),flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for index,future in enumerate(as_completed([pool.submit(upload,item) for item in pending]),1):
            key,result=future.result();progress[key]=result
            progress_file.write_text(json.dumps(progress,ensure_ascii=False,indent=2),encoding='utf-8')
            if index%25==0 or not result['success']:print(json.dumps({'completed_pending':index,'total_pending':len(pending),'last_success':result['success']}),flush=True)
    progress_file.write_text(json.dumps(progress,ensure_ascii=False,indent=2),encoding='utf-8')
    failed=[item['key'] for item in manifest['files'] if not(progress.get(item['key'],{}).get('success') and progress[item['key']].get('sha256')==item['sha256'])]
    print(json.dumps({'total':len(manifest['files']),'failed':len(failed)}),flush=True)
    if failed:raise SystemExit(1)


if __name__=='__main__':main()
