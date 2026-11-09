"""已停用：cloudflare/src/legacy 已不存在。

本脚本会把旧统计模块复制进 cloudflare/src/legacy，可能在新结构中产生第二套
统计实现。脚本现在直接退出，不做任何写入。
"""

import sys


def main():
    """提示停用原因并返回非零状态码。"""
    print('已停用：cloudflare/src/legacy 已不存在，统计统一由 knowledge_stats.py 与 analytics.py 提供。')
    print('如需扩展统计，请直接修改 cloudflare/src 下的正式实现。')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
