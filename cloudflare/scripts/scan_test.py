"""整页识别录入的本地测试。

后续任务会在本脚本中追加解析、入库与接口测试。运行：

    python cloudflare/scripts/scan_test.py
"""

import asyncio
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import scan  # noqa: E402
import scan_model  # noqa: E402


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def run(coroutine):
    """同步运行一个协程。"""
    return asyncio.run(coroutine)


class FakeEnv:
    """伪造 Worker 的 env，健康检查接口不访问任何绑定。"""


class FakeRequest:
    """伪造 FastAPI 的 Request，只提供 scope。"""

    def __init__(self):
        self.scope = {'env': FakeEnv()}


class FakeOcrClient:
    """替换 scan.ocr_client 的假客户端，健康检查返回预设结果。"""

    def __init__(self, health_result):
        self.health_result = health_result

    async def fetch_health(self, env, timeout_seconds):
        """返回预设的 (状态码, JSON)。"""
        return self.health_result


# ---------------------------------------------------------------- 健康检查

def test_interpret_health():
    """只有 200、ok 为真、契约版本为 1 才算可用。"""
    assert scan_model.interpret_health(200, {'ok': True, 'contract': 1, 'ollama': True}) is True
    assert scan_model.interpret_health(200, {'ok': False, 'contract': 1, 'ollama': False}) is False
    assert scan_model.interpret_health(200, {'ok': True, 'contract': 2}) is False
    assert scan_model.interpret_health(200, None) is False
    assert scan_model.interpret_health(401, {'ok': False}) is False
    assert scan_model.interpret_health(0, None) is False


def test_health_endpoint_hides_host_details():
    """健康检查接口只返回 available，不透出主机的任何字段。"""
    scan.ocr_client = FakeOcrClient((200, {'ok': True, 'contract': 1, 'model': 'x'}))
    assert run(scan.health(FakeRequest())) == {'available': True}
    scan.ocr_client = FakeOcrClient((0, None))
    assert run(scan.health(FakeRequest())) == {'available': False}


TESTS = [
    test_interpret_health,
    test_health_endpoint_hides_host_details,
]


def check(name, function):
    """运行单个测试，打印 PASS/FAIL，返回是否通过。"""
    try:
        function()
    except Exception:
        print('FAIL', name)
        traceback.print_exc()
        return False
    print('PASS', name)
    return True


def main():
    """运行全部测试并打印总数；有失败时以非零状态退出。"""
    configure_output()
    results = [check(function.__name__, function) for function in TESTS]
    passed = sum(1 for ok in results if ok)
    print('%d/%d passed' % (passed, len(results)))
    if passed != len(results):
        sys.exit(1)


if __name__ == '__main__':
    main()
