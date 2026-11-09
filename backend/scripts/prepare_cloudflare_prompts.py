"""提取现有纯提示词函数，避免在 Worker 加载同步 SDK。"""

import ast
from pathlib import Path


def main():
    """只打包明确列出的无网络纯函数。"""
    root=Path(__file__).resolve().parents[2]
    tree=ast.parse((root/'backend/app/services/llm.py').read_text(encoding='utf-8-sig'))
    original=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='LLMService')
    wanted={'_build_prompt','_build_learning_report_prompt','_get_grade_name'}
    methods=[node for node in original.body if isinstance(node,ast.FunctionDef) and node.name in wanted]
    if {node.name for node in methods}!=wanted:raise RuntimeError('提示词函数发生变化，请人工检查')
    generated=ast.Module(body=[ast.ImportFrom(module='typing',names=[ast.alias(name='Optional')],level=0),ast.ClassDef(name='PromptLibrary',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
    (root/'cloudflare/src/prompts.py').write_text('"""从现有服务提取的纯提示词模板。"""\n'+ast.unparse(ast.fix_missing_locations(generated))+'\n',encoding='utf-8')
    print('Prepared existing prompt templates.')


if __name__=='__main__':main()
