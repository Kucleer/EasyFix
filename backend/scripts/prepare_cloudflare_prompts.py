"""已停用：cloudflare/src/prompts.py 自两级知识点改造起为手写源。

本脚本原先会从 backend/app/services/llm.py 重新生成 prompts.py，从而覆盖
按一级/二级知识点改造后的提示词。为避免误操作，脚本现在直接退出，不做任何写入。
"""

import sys


def main():
    """提示停用原因并返回非零状态码。"""
    print('已停用：cloudflare/src/prompts.py 是手写源，不再从 backend/app/services/llm.py 生成。')
    print('如需修改提示词，请直接编辑 cloudflare/src/prompts.py 并运行知识点不变量测试。')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
