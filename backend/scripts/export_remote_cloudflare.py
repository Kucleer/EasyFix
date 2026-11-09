"""下载远端 D1 快照，隐藏 CLI 输出中的临时签名下载链接。"""
import argparse
from pathlib import Path
import subprocess


def main():
    """保存导出而不将短期访问凭证输出到日志。"""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    output=args.snapshot.resolve()/'remote.sql'
    result=subprocess.run(['node',str(root/'cloudflare/tools/cli.cjs'),'d1','export','easyfix','--config',str(root/'cloudflare/wrangler.jsonc'),'--remote','--output',str(output),'--skip-confirmation'],cwd=root,capture_output=True,timeout=180)
    if result.returncode:raise RuntimeError('远端快照下载失败，请检查授权和连接')
    print('Remote snapshot downloaded; temporary URL hidden.')


if __name__=='__main__':main()
