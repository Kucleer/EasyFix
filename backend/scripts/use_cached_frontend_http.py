"""将现有 axios 导入接入统一请求缓存，不改动业务调用参数。"""

from pathlib import Path


def main():
    """只替换默认 axios 导入，保留全部现有页面修改。"""
    root=Path(__file__).resolve().parents[2]/'frontend/src'
    changed=[]
    for path in [*root.rglob('*.js'),*root.rglob('*.vue')]:
        if path==root/'api/http.js':continue
        source=path.read_text(encoding='utf-8-sig')
        updated=source.replace("import axios from 'axios'","import axios from '@/api/http'").replace('import axios from "axios"','import axios from "@/api/http"')
        if source!=updated:path.write_text(updated,encoding='utf-8');changed.append(path.relative_to(root).as_posix())
    print('Updated HTTP imports: '+', '.join(changed))


if __name__=='__main__':main()
