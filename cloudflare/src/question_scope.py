"""统计和选题共用的"算数的题"条件：没删除且已核对（counted）、题干不为空（stem_ready）、年级不低于默认年级（grade_ready）。

凡是数题目、算比例、挑题目的查询都引用这里，条件只写这一处。
"""

COUNTED = "deleted=0 AND review_status='approved'"


def counted(alias: str) -> str:
    """返回带表别名的条件，如 counted('q') -> "q.deleted=0 AND q.review_status='approved'"。"""
    return "%s.deleted=0 AND %s.review_status='approved'" % (alias, alias)


# 去首尾空白时要去掉的字符：空格、制表符、换行、回车（SQLite 的 TRIM 默认只去空格）
BLANKS = "' '||char(9)||char(10)||char(13)"


def stem_ready(alias: str) -> str:
    """返回"题干不为空"的 SQL 条件：解析后的题干为空时看原题文字，去掉首尾空白后不能为空。

    例：stem_ready('q') 得到的条件放在 WHERE 或 SELECT 里都可以，结果是真/假。
    """
    parsed = 'NULLIF(TRIM(%s.parsed_question, %s), \'\')' % (alias, BLANKS)
    return "TRIM(COALESCE(%s, %s.original_text, ''), %s)<>''" % (parsed, alias, BLANKS)


def grade_ready(alias: str, min_grade: int | None) -> tuple[str, list]:
    """返回"年级不低于默认年级"的 SQL 条件和参数。

    年级为空的题算当前年级；min_grade 为空（没设置默认年级）时不按年级筛，返回 ('1=1', [])。
    """
    if min_grade is None:
        return '1=1', []
    return '(%s.grade IS NULL OR %s.grade>=?)' % (alias, alias), [min_grade]


def current_student_id(request) -> int:
    """当前学生；目前固定返回 1，多学生上线时只改这里。"""
    return 1
