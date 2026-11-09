"""构建独立云端发布目录，保留原 frontend/dist 和本地服务。"""

from pathlib import Path
import shutil
import subprocess


def main():
    """校验生成目录边界后构建，并加入网关与固定版本公式字体。"""
    root=Path(__file__).resolve().parents[2]
    output=(root/'tmp/cloudflare-pages-build').resolve()
    if not output.is_relative_to((root/'tmp').resolve()) or output.name!='cloudflare-pages-build':raise RuntimeError('构建目录越界')
    subprocess.run(['node',str(root/'frontend/node_modules/vite/bin/vite.js'),'build','--outDir',str(output),'--emptyOutDir'],cwd=root/'frontend',check=True)
    shutil.copy2(root/'cloudflare/pages/_worker.js',output/'_worker.js')
    shutil.copytree(root/'backend/app/static/katex/fonts',output/'assets/math/v0.19.0/fonts',dirs_exist_ok=True)
    print('Prepared cloud frontend at '+str(output))


if __name__=='__main__':main()
