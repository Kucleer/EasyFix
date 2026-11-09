"""盘点所有实际上传文件及历史上传目录，生成可恢复的 R2 映射。"""

from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import mimetypes
import os
import re
from pathlib import Path
import sys


def main():
    """主挂载目录保持原路径，其他历史目录保留归档路径，不猜测关联。"""
    root=Path(__file__).resolve().parents[2];backend=root/'backend'
    sys.path.insert(0,str(backend));os.chdir(backend)
    from app.config import get_settings
    primary=Path(get_settings().UPLOAD_DIR).resolve()
    entries={};collisions=[];skipped=[]
    sources=[(primary,''),(backend/'uploads',''),(root/'uploads','legacy-root-uploads/'),(backend/'backend/uploads','legacy-nested-uploads/')]
    for source,prefix in sources:
        source=source.resolve()
        if not source.exists():continue
        for path in sorted(source.rglob('*')):
            if not path.is_file():continue
            real=path.resolve()
            if not real.is_relative_to(source):skipped.append(str(path));continue
            if source!=primary and real.is_relative_to(primary):continue
            key=prefix+path.relative_to(source).as_posix()
            legacy_key=key
            if key.startswith('audio/words/') and path.suffix.lower() in ('.mp3','.wav') and not re.fullmatch(r'[a-z0-9_ -]+',path.stem.lower()):
                key='audio/words/'+hashlib.sha256(path.stem.lower().encode()).hexdigest()+path.suffix.lower()
            with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if key in entries:
                if entries[key]['sha256']==digest:continue
                collisions.append(key);key='legacy-backend-uploads/'+path.relative_to(source).as_posix()
            entries[key]={'key':key,'legacy_key':legacy_key,'path':str(path),'size':path.stat().st_size,'sha256':digest,'content_type':mimetypes.guess_type(path)[0] or 'application/octet-stream'}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    report={'created_at_utc':stamp,'files':list(entries.values()),'collisions_archived':collisions,'skipped_external_links':skipped}
    output=root/'backups'/('cloudflare_files_'+stamp+'.json');output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    audio={}
    for item in sorted(entries.values(),key=lambda item:item['path'].lower().endswith('.wav')):
        if item['legacy_key'].startswith('audio/words/'):
            audio[Path(item['path']).stem.lower()]=item['key']
    (root/'cloudflare/src/audio_index.py').write_text('"""历史音频缓存路径索引，避免重复查找对象。"""\nAUDIO_INDEX='+repr(audio)+'\n',encoding='utf-8')
    print(json.dumps({'manifest':str(output),'files':len(entries),'bytes':sum(item['size'] for item in entries.values()),'types':dict(Counter(item['content_type'].split('/')[0] for item in entries.values())),'collisions':len(collisions),'skipped_external_links':len(skipped)}))


if __name__=='__main__':main()
