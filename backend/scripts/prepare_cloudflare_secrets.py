"""只在被忽略的本地目录准备部署密钥，不输出密钥内容。"""

import json
from pathlib import Path
import secrets
import sys


def main():
    """沿用现有访问密码，生成独立的云端签名与 Agent 密钥。"""
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / 'backend'))
    from app.access_config import ACCESS_PASSWORD
    output = root / 'tmp/cloudflare-config/easyfix-secrets.json'
    existing = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
    existing.setdefault('SESSION_SECRET', secrets.token_urlsafe(48))
    existing.setdefault('ACCESS_TOKEN', secrets.token_urlsafe(48))
    existing['ACCESS_PASSWORD'] = ACCESS_PASSWORD
    for name, key in [('llm', 'LLM_CONFIG'), ('app', 'APP_CONFIG')]:
        source = root / 'backend/config' / (name + '.json')
        if source.is_file():
            existing[key] = source.read_text(encoding='utf-8-sig')
    output.write_text(json.dumps(existing), encoding='utf-8')
    (output.parent/'easyfix-pages-secrets.json').write_text(json.dumps({'SESSION_SECRET':existing['SESSION_SECRET'],'ACCESS_TOKEN':existing['ACCESS_TOKEN']}),encoding='utf-8')
    print('Deployment secrets prepared locally; contents hidden.')


if __name__ == '__main__':
    main()
