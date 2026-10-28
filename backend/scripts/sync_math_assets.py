"""把锁定版本的 KaTeX 离线资源复制给 Python PDF 服务。"""

import json
from pathlib import Path
import shutil


def main():
    """检查前端锁定版本并复制必要脚本、样式、字体及许可证。"""
    root = Path(__file__).resolve().parents[2]
    source = root / 'frontend/node_modules/katex'
    expected = json.loads((root / 'frontend/package.json').read_text(encoding='utf-8'))['dependencies']['katex']
    actual = json.loads((source / 'package.json').read_text(encoding='utf-8'))['version']
    if expected != actual:
        raise RuntimeError(f'KaTeX 版本不一致：需要 {expected}，实际 {actual}')
    target = root / 'backend/app/static/katex'
    target.mkdir(parents=True, exist_ok=True)
    for name in ['katex.min.js', 'katex.min.css', 'contrib/auto-render.min.js']:
        output = target / Path(name).name
        shutil.copy2(source / 'dist' / name, output)
    shutil.copytree(source / 'dist/fonts', target / 'fonts', dirs_exist_ok=True)
    shutil.copy2(source / 'LICENSE', target / 'LICENSE')
    (target / 'version.txt').write_text(actual + '\n', encoding='utf-8')
    print(f'KaTeX {actual} 离线资源已同步')


if __name__ == '__main__':
    main()
