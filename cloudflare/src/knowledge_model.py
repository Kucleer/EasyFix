"""两级知识点目录的纯逻辑：规范键、错误码映射与树结构。

本模块不依赖 FastAPI，便于本地 sqlite 不变量测试直接导入验证。
"""

import re
import unicodedata

# 触发器错误码到 HTTP 状态码的固定映射，避免全部落入通用 500。
ERROR_STATUS = {
    'KP_LEVEL': 422,
    'KP_SUBJECT': 422,
    'KP_NAME': 422,
    'KP_STRUCT': 422,
    'KP_MOVE': 409,
    'KP_CHILD': 409,
    'KP_INUSE': 409,
    'KP_GUARD': 409,
    'KP_VERSION': 409,
    'KP_STATE': 503,
}

# 只有前缀没有中文说明时使用的中文兜底文案。
ERROR_TEXT = {
    'KP_LEVEL': '知识点层级或父级不合法',
    'KP_SUBJECT': '知识点与题目或父级学科不一致',
    'KP_NAME': '知识点名称不能为空或重复',
    'KP_STRUCT': '题目主考点结构校验失败，请刷新后重试',
    'KP_MOVE': '有子级或题目关联的知识点不能移动或改层级',
    'KP_CHILD': '一级知识点仍有有效二级，不能删除',
    'KP_INUSE': '知识点或学科仍被有效数据引用，不能删除',
    'KP_GUARD': '数据已被其他操作修改，请刷新后重试',
    'KP_VERSION': '分类已变更，请刷新后重试',
    'KP_STATE': '系统维护中，请稍后再试',
}

CODE_PATTERN = re.compile(r'(KP_[A-Z_]+)')
LEVELS = (1, 2)
VALID_SOURCES = ('manual', 'migration', 'agent')


def normalize_name_key(name):
    """将名称规范化为稳定比较键：NFKC、去首尾空白、压缩空白、英文小写。"""
    if not isinstance(name, str):
        return ''
    text = unicodedata.normalize('NFKC', name).strip()
    return re.sub(r'\s+', ' ', text).casefold()


def clean_name(name):
    """去除首尾空白但保留原始全半角，供展示使用。"""
    return unicodedata.normalize('NFKC', name).strip() if isinstance(name, str) else ''


def error_code(message):
    """从 D1 异常消息中提取固定的 KP 错误码。"""
    found = CODE_PATTERN.search(str(message or ''))
    return found.group(1) if found else None


def map_error(message):
    """把 D1 异常转换为 (状态码, 中文说明)；无法识别时返回 None。"""
    code = error_code(message)
    if code is None:
        return None
    status = ERROR_STATUS.get(code, 500)
    text = str(message)
    marker = code + ':'
    detail = text.split(marker, 1)[1].strip() if marker in text else ''
    if not detail:
        detail = ERROR_TEXT.get(code, '知识点操作失败')
    return status, detail


def build_tree(rows):
    """把平铺的目录行组装为两级树，一级按 sort_order、id 排序。"""
    parents = {}
    children = {}
    for row in rows:
        if row.get('level') == 1:
            parents[row['id']] = {**row, 'children': []}
        elif row.get('level') == 2 and row.get('parent_id') is not None:
            children.setdefault(row['parent_id'], []).append(row)
    def order(item):
        return (item.get('sort_order') or 0, item.get('id') or 0)
    for parent_id, items in children.items():
        if parent_id in parents:
            parents[parent_id]['children'] = sorted(items, key=order)
    return sorted(parents.values(), key=order)


def projection_name(points):
    """兼容投影只输出主考点二级名称，不拼接多选字符串。"""
    for point in points or []:
        if point.get('is_primary'):
            return point.get('name')
    return None


def normalize_id_list(value):
    """校验 ID 列表：所有元素必须是正整数且不重复；非法时返回 None。"""
    if not isinstance(value, list):
        return None
    if any(type(item) is not int or item <= 0 for item in value):
        return None
    return list(dict.fromkeys(value))
