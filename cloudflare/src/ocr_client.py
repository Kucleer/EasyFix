"""通过 Workers VPC 绑定调用本机识别主机。

所有函数都不抛异常：绑定或口令缺失、连不上、超时、返回非 JSON 时，
调用方只会拿到 (0, None) 或 (状态码, None)。js / pyodide 只在函数内导入，
这样本模块在普通 CPython（测试、本地开发服务）下也能导入。
"""

import json

OCR_BINDING = 'OCR_HOST'
KEY_SECRET = 'OCR_SHARED_KEY'
BASE_URL = 'http://ocr-host'


async def _request(env, path, method, headers, body, timeout_seconds):
    """向识别主机发一次请求，返回 (状态码, 解析后的 JSON 或 None)；任何异常都收在这里。"""
    try:
        binding = getattr(env, OCR_BINDING, None)
        key = getattr(env, KEY_SECRET, None)
        if binding is None or key is None:
            return 0, None
        from js import AbortSignal
        options = {
            'method': method,
            'headers': dict(headers, **{'X-EasyFix-OCR-Key': str(key)}),
            'signal': AbortSignal.timeout(int(timeout_seconds * 1000)),
        }
        if body is not None:
            options['body'] = body
        response = await binding.fetch(BASE_URL + path, **options)
        status = int(response.status)
        try:
            parsed = json.loads(await response.text())
        except ValueError:
            return status, None
        return status, parsed if isinstance(parsed, dict) else None
    except Exception:
        return 0, None


async def fetch_health(env, timeout_seconds):
    """查询主机健康状态，返回 (状态码, JSON)。"""
    return await _request(env, '/health', 'GET', {}, None, timeout_seconds)


async def fetch_ocr(env, content, content_type, mode, timeout_seconds):
    """把整页图片字节发给主机识别，返回 (状态码, JSON)。"""
    try:
        from pyodide.ffi import to_js
        body = to_js(content)
    except Exception:
        return 0, None
    return await _request(env, '/ocr?mode=' + str(mode), 'POST',
                          {'Content-Type': content_type}, body, timeout_seconds)


async def read_image(env, key):
    """从私有 R2 读取图片，返回 (字节, 类型)；不存在或读取失败返回 None。"""
    try:
        from js import Uint8Array
        obj = await env.IMAGES.get(key)
        if obj is None:
            return None
        content = Uint8Array.new(await obj.arrayBuffer()).to_py().tobytes()
        content_type = getattr(obj.httpMetadata, 'contentType', None) or 'application/octet-stream'
        if content_type == 'image/jpg':
            content_type = 'image/jpeg'
        return content, content_type
    except Exception:
        return None
