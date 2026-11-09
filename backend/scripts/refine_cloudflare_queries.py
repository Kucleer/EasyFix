"""已停用：软删除过滤等替换已固化在 cloudflare/src 源码中。

本脚本原先会对 cloudflare/src 做字符串替换，重跑会覆盖两级知识点改造后的
查询语句。脚本现在直接退出，不做任何写入。
"""

import sys


def main():
    """提示停用原因并返回非零状态码。"""
    print('已停用：cloudflare/src 的查询语句已固化为手写源码，不再做批量字符串替换。')
    print('如需调整查询，请直接编辑 cloudflare/src 下对应模块并运行验证脚本。')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
