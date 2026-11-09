"""保留阅读包的来源说明，随代码部署，不增加每次读取的存储调用。"""

import json
from pathlib import Path


def main():
    """按原后端规则生成只读来源索引。"""
    root=Path(__file__).resolve().parents[2];result={}
    for path in (root/'backend/data/reading').glob('grade6-*.json'):
        pack=json.loads(path.read_text(encoding='utf-8'))
        for item in pack.get('passages',[]):result[pack['pack_id']+':'+item['id']]=item['provenance']
    (root/'cloudflare/src/provenance.py').write_text('"""随代码分发的阅读包来源索引。"""\nPROVENANCE='+repr(result)+'\n',encoding='utf-8')
    print({'provenance_records':len(result)})


if __name__=='__main__':main()
