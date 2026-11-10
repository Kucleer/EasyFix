"""统计和选题共用的"算数的题"条件：没删除，并且已通过核对。

凡是数题目、算比例、挑题目的查询都引用这里，条件只写这一处。
"""

COUNTED = "deleted=0 AND review_status='approved'"


def counted(alias: str) -> str:
    """返回带表别名的条件，如 counted('q') -> "q.deleted=0 AND q.review_status='approved'"。"""
    return "%s.deleted=0 AND %s.review_status='approved'" % (alias, alias)


def current_student_id(request) -> int:
    """当前学生；目前固定返回 1，多学生上线时只改这里。"""
    return 1
