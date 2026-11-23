"""防漏测试：后端每条碰学生数据表的 SQL，都必须带 student_id 条件。

做法：用 ast 读出 cloudflare/src/*.py 里的所有字符串（包括用 + 或 % 拼起来的、f-string 的固定部分），
只要字符串里出现 FROM / JOIN / UPDATE / INTO 学生表，同一个字符串里就必须出现 student_id。
确实不需要过滤的个别语句，在字符串所在行或上一行写注释 "# scope-ok: 理由"，
并在 ALLOWED_EXEMPTIONS 里登记这个文件的豁免条数（新增豁免要改这里，评审时能看到）。

运行：

    python cloudflare/scripts/student_scope_test.py
"""

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'

# 带 student_id 的学生数据表：读写都要按学生过滤
STUDENT_TABLES = (
    'question', 'error_book', 'word', 'word_review', 'word_review_session', 'practice_set', 'learning_report',
    'reading_passage', 'tag', 'reward', 'redemption', 'star_balance', 'star_record', 'achievement_progress',
    'paper', 'scan_page', 'weekly_report', 'flip_log', 'mastery_adjustment',
)
# 有 student_id 列但按共用目录处理的表（只有管理员能改，大家都能读），不检查
SHARED_TABLES = ('star_action', 'achievement', 'textbook_section')

TABLE_PATTERN = re.compile(r'\b(?:FROM|JOIN|UPDATE|INTO)\s+(%s)\b' % '|'.join(STUDENT_TABLES), re.IGNORECASE)
EXEMPT_MARK = '# scope-ok:'

# 每个文件允许的豁免条数：{'文件名.py': 条数}
ALLOWED_EXEMPTIONS = {'catalog.py': 1, 'intake.py': 3, 'knowledge.py': 3, 'questions.py': 3, 'scan.py': 9, 'similar.py': 1}


def string_parts(node):
    """收集一个表达式里所有固定的字符串片段（+ 拼接、% 格式化的左边、f-string 的固定部分）。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [value.value for value in node.values if isinstance(value, ast.Constant) and isinstance(value.value, str)]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return string_parts(node.left) + string_parts(node.right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return string_parts(node.left)
    return []


def is_string_expression(node):
    """判断节点是不是"字符串表达式"（常量、f-string、字符串的 + 或 %）。"""
    return bool(string_parts(node)) and isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp))


def sql_strings(tree):
    """找出文件里所有最外层的字符串表达式（被别的字符串表达式包住的不再单独算），返回 [(行号, 拼好的文字)]。"""
    inner = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and is_string_expression(node):
            for child in (node.left, node.right):
                inner.add(id(child))
        if isinstance(node, ast.JoinedStr):
            for child in node.values:
                inner.add(id(child))
    found = []
    for node in ast.walk(tree):
        if id(node) in inner or not is_string_expression(node):
            continue
        found.append((node.lineno, ''.join(string_parts(node))))
    return found


def is_exempt(lines, lineno):
    """字符串所在行或上一行写了 scope-ok 注释就算豁免。"""
    for index in (lineno - 1, lineno - 2):
        if 0 <= index < len(lines) and EXEMPT_MARK in lines[index]:
            return True
    return False


def scan_file(path):
    """扫描一个文件，返回 (没过滤的位置列表, 豁免条数)。位置是 '文件:行号 表名'。"""
    source = path.read_text(encoding='utf-8')
    lines = source.split('\n')
    problems, exemptions = [], 0
    for lineno, text in sql_strings(ast.parse(source)):
        tables = sorted({match.group(1).lower() for match in TABLE_PATTERN.finditer(text)})
        if not tables or 'student_id' in text:
            continue
        if is_exempt(lines, lineno):
            exemptions += 1
            continue
        problems.append('%s:%d %s' % (path.name, lineno, ','.join(tables)))
    return problems, exemptions


def scan_all():
    """扫描全部后端源码，返回 (问题列表, {文件名: 豁免条数})。"""
    problems, exemptions = [], {}
    for path in sorted(SRC.glob('*.py')):
        found, exempt = scan_file(path)
        problems.extend(found)
        if exempt:
            exemptions[path.name] = exempt
    return problems, exemptions


def test_scanner_sees_concatenated_sql():
    """扫描器能识别拼接出来的 SQL，并认出其中的 student_id。"""
    tree = ast.parse("a = 'SELECT * FROM question q ' + cond('q') + ' AND q.student_id=?'\n"
                     "b = 'SELECT id FROM word WHERE id=%s' % x\n"
                     "c = f'UPDATE practice_set SET a=1 WHERE id={i}'\n"
                     "d = 'SELECT * FROM question_tag'\n")
    texts = [text for _, text in sql_strings(tree)]
    assert any('student_id' in t and 'question q' in t for t in texts)
    flagged = [t for t in texts if TABLE_PATTERN.search(t) and 'student_id' not in t]
    assert len(flagged) == 2, flagged   # word 和 practice_set；question_tag 不是学生表


def test_every_student_query_is_scoped():
    """所有碰学生数据表的 SQL 都带 student_id（或有登记的豁免）。"""
    problems, _ = scan_all()
    assert not problems, '下面这些 SQL 没按学生过滤：\n  ' + '\n  '.join(problems)


def test_exemption_counts():
    """豁免条数和 ALLOWED_EXEMPTIONS 登记的一致。"""
    _, exemptions = scan_all()
    assert exemptions == ALLOWED_EXEMPTIONS, exemptions


TESTS = [test_scanner_sees_concatenated_sql, test_every_student_query_is_scoped, test_exemption_counts]


def main():
    """运行全部测试；失败时打印原因并以非零状态退出。"""
    failed = 0
    for test in TESTS:
        try:
            test()
            print('PASS', test.__name__)
        except AssertionError as error:
            failed += 1
            print('FAIL', test.__name__)
            print(error)
    print('%d 通过，%d 失败' % (len(TESTS) - failed, failed))
    sys.exit(failed)


if __name__ == '__main__':
    main()
