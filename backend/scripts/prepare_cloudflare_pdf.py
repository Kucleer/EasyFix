"""复制现有生产数学渲染器和固定版本 KaTeX，不转换历史题目。"""

from pathlib import Path
import shutil


def main():
    """为渲染服务与静态资源目录准备一致的公式资源。"""
    root=Path(__file__).resolve().parents[2]
    source=root/'backend/app/static/katex'
    output=root/'cloudflare/pdf/assets';output.mkdir(parents=True,exist_ok=True)
    for name,target in [('katex.min.js','katex.txt'),('auto-render.min.js','auto-render.txt'),('katex.min.css','katex-css.txt')]:
        shutil.copy2(source/name,output/target)
    shutil.copy2(root/'shared/math-text.mjs',output/'math-text.txt')
    fonts=root/'tmp/cloudflare-pages-build/assets/math/v0.19.0/fonts'
    shutil.copytree(source/'fonts',fonts,dirs_exist_ok=True)
    print('Prepared production math renderer and fonts.')


if __name__=='__main__':main()
