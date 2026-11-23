"""测试和本机测试环境共用的默认登录身份：1 号家庭（管理员）的 1 号学生。"""

DEFAULT_IDENTITY = {'user_id': 1, 'username': 'admin', 'is_admin': True, 'version': 1, 'student_id': 1}


def default_identity():
    """返回一份默认身份的副本（避免测试之间互相改到）。"""
    return dict(DEFAULT_IDENTITY)
