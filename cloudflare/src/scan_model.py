"""整页识别录入的纯逻辑（不碰数据库和网络）。"""

CONTRACT_VERSION = 1
HEALTH_TIMEOUT_SECONDS = 3


def interpret_health(status, body):
    """解读主机健康检查结果：200、ok 为真、契约版本匹配才算可用。"""
    if status != 200 or not isinstance(body, dict):
        return False
    return body.get('ok') is True and body.get('contract') == CONTRACT_VERSION
