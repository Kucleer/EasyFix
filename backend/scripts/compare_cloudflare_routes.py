"""静态比对当前业务路由与云端实现，避免漏迁移接口。"""

import ast
from pathlib import Path
import re


def routes(path):
    """提取一个文件中声明的 HTTP 方法与路径。"""
    tree=ast.parse(path.read_text(encoding='utf-8-sig'));prefix='';result=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='APIRouter':
            for keyword in node.keywords:
                if keyword.arg=='prefix':prefix=ast.literal_eval(keyword.value)
    for node in tree.body:
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
        for decorator in node.decorator_list:
            if isinstance(decorator,ast.Call) and isinstance(decorator.func,ast.Attribute) and decorator.func.attr in ('get','post','put','delete','patch'):
                result.append((decorator.func.attr.upper(),prefix+ast.literal_eval(decorator.args[0]),path.name,node.lineno))
    return result


def normalized(route):
    """参数名称不影响接口兼容性。"""
    return route[0],re.sub(r'\{[^}]+\}','{}',route[1])


def main():
    """生成代码覆盖清单，运行验证单独记录，不把实现等同验收。"""
    root=Path(__file__).resolve().parents[2]
    original=[row for path in (root/'backend/app/routers').glob('*.py') for row in routes(path)]
    cloud=[row for path in (root/'cloudflare/src').glob('*.py') for row in routes(path)]
    tree=ast.parse((root/'cloudflare/src/catalog.py').read_text(encoding='utf-8'))
    kinds=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='CATALOG' for target in node.targets))
    for kind in kinds:
        cloud.extend((method,'/api/'+kind+suffix,'catalog.py',0) for method,suffix in [('GET',''),('POST',''),('GET','/{item_id}'),('PUT','/{item_id}'),('DELETE','/{item_id}')])
    actual={normalized(row) for row in cloud};missing=[row for row in original if normalized(row) not in actual]
    lines=['# Cloudflare API 迁移清单','','以下复选框代表已有对应代码；不等同于全部运行场景均已验收。运行验证见迁移记录。','']
    for row in sorted(original):
        note='（旧调试接口返回410）' if '/debug/' in row[1] else '（改为播放时生成并缓存，减少调用）' if row[1].endswith('/generate-audio') else ''
        lines.append(('- ['+('x' if normalized(row) in actual else ' ')+'] `'+row[0]+' '+row[1]+'` '+note).rstrip())
    (root/'docs/cloudflare-api-checklist.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print({'original_routes':len(original),'implemented':len(original)-len(missing),'missing':[(row[0],row[1]) for row in missing]})
    if missing:raise SystemExit(1)


if __name__=='__main__':main()
