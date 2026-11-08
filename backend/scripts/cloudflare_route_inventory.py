"""静态读取当前路由，避免导入应用时触发建表和初始化。"""

import ast
import json
from pathlib import Path


def main():
    """生成逐接口迁移待办，保留现有源文件与行号。"""
    root = Path(__file__).resolve().parents[2]
    rows = []
    for path in sorted((root / 'backend/app/routers').glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        prefix = ''
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'APIRouter':
                for keyword in node.keywords:
                    if keyword.arg == 'prefix':
                        prefix = ast.literal_eval(keyword.value)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr in ('get', 'post', 'put', 'delete', 'patch'):
                    route = prefix + ast.literal_eval(decorator.args[0])
                    rows.append({'method': decorator.func.attr.upper(), 'path': route,
                                 'source': path.relative_to(root).as_posix(), 'line': node.lineno,
                                 'function': node.name, 'status': 'pending'})
    output = root / 'docs/cloudflare-api-checklist.md'
    output.write_text('# Cloudflare API 迁移待办\n\n由当前代码静态生成，共 ' + str(len(rows)) + ' 个业务接口；不包括 main.py 的健康与认证入口。\n\n' + '\n'.join('- [ ] `' + row['method'] + ' ' + row['path'] + '` — ' + row['source'] + ':' + str(row['line']) for row in rows) + '\n', encoding='utf-8')
    print(json.dumps({'routes': len(rows), 'checklist': str(output)}))


if __name__ == '__main__':
    main()
