"""给 1 号用户（管理员）设置登录名和密码；多家庭账号上线时运行一次，以后忘了密码也用它重设。

密码只在终端里输入（不回显），不写进文件、命令历史和日志。哈希格式与网关
cloudflare/pages/password.js 完全相同：pbkdf2-sha256$迭代次数$盐(base64)$哈希(base64)。

运行（仓库根目录）：

    python backend/scripts/set_admin_password.py            # 正式执行
    python backend/scripts/set_admin_password.py --dry-run  # 只打印要执行的 SQL（哈希用 *** 代替）
"""

import argparse
import base64
import getpass
import hashlib
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[2]
# 迭代次数与网关 password.js 的 PBKDF2_ITERATIONS 保持一致
ITERATIONS = 100000
USERNAME_PATTERN = re.compile(r'^[a-z0-9_]{3,20}$')
MIN_PASSWORD_LENGTH = 10


def hash_password(password: str, iterations: int, salt: bytes) -> str:
    """按网关相同的格式算出密码哈希。"""
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations, dklen=32)
    return 'pbkdf2-sha256$%d$%s$%s' % (iterations, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def build_sql(username: str, password_hash: str, now_text: str) -> str:
    """生成更新 1 号用户的 SQL；会话版本加 1，旧登录全部失效。"""
    # 登录名已按正则校验，哈希只含 base64 字符和 $，都不含单引号，直接拼进 SQL 是安全的
    return ("UPDATE app_user SET username='%s', password_hash='%s', session_version=session_version+1, "
            "updated_at='%s' WHERE id=1;" % (username, password_hash, now_text))


def read_inputs():
    """在终端里读登录名和两遍密码；不合格时返回 None 并说明原因。"""
    username = input('管理员登录名（小写字母、数字、下划线，3–20 位）：').strip()
    if not USERNAME_PATTERN.match(username):
        print('登录名格式不对。')
        return None
    password = getpass.getpass('新密码（至少 %d 位，不显示）：' % MIN_PASSWORD_LENGTH)
    if len(password) < MIN_PASSWORD_LENGTH:
        print('密码太短。')
        return None
    if getpass.getpass('再输一遍：') != password:
        print('两次输入不一致。')
        return None
    return username, password


def main():
    """读输入、生成 SQL，写进被忽略的 tmp 目录后用 wrangler 在远程 D1 执行，执行完删除临时文件。"""
    parser = argparse.ArgumentParser(description='设置管理员登录名和密码')
    parser.add_argument('--dry-run', action='store_true', help='只打印 SQL，不执行')
    args = parser.parse_args()
    inputs = read_inputs()
    if inputs is None:
        sys.exit(1)
    username, password = inputs
    now_text = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    sql = build_sql(username, hash_password(password, ITERATIONS, os.urandom(16)), now_text)
    if args.dry_run:
        print(re.sub(r"password_hash='[^']*'", "password_hash='***'", sql))
        return
    folder = ROOT / 'tmp' / 'cloudflare-config'
    folder.mkdir(parents=True, exist_ok=True)
    sql_file = folder / 'set_admin_password.sql'
    try:
        sql_file.write_text(sql, encoding='utf-8')
        command = ['node', str(ROOT / 'cloudflare' / 'tools' / 'cli.cjs'), 'd1', 'execute', 'easyfix',
                   '--config', str(ROOT / 'cloudflare' / 'wrangler.jsonc'), '--remote', '--file', str(sql_file), '--yes']
        result = subprocess.run(command, cwd=ROOT)
    finally:
        sql_file.unlink(missing_ok=True)
    if result.returncode != 0:
        print('执行失败，请看上面的 wrangler 输出。')
        sys.exit(result.returncode)
    print('已设置管理员 %s 的密码，旧的登录全部失效。' % username)


if __name__ == '__main__':
    main()
