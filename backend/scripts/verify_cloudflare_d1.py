"""核对远程 D1 每张表的数量与本地导出清单。"""

import json
from pathlib import Path
import subprocess
import sys


def main():
    """调用 Wrangler 只读查询并严格比较全部表计数及外键。"""
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    query = ';'.join('SELECT ' + "'" + name + "' AS table_name,COUNT(*) AS count FROM \"" + name + '\"' for name in manifest['tables'])
    query_file = Path(sys.argv[1]).resolve().parent / 'verify-counts.sql'
    query_file.write_text(query + ';', encoding='utf-8')
    result = subprocess.run(['node', str(root / 'tmp/cloudflare-cli.cjs'), 'd1', 'execute', 'easyfix', '--remote', '--command', query, '--json'], capture_output=True, text=True, encoding='utf-8', cwd=root)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    parsed = json.loads(result.stdout)
    actual = {row['table_name']: row['count'] for statement in parsed for row in statement['results']}
    if actual != manifest['tables']:
        raise RuntimeError('远程表计数与导出清单不一致')
    check = subprocess.run(['node', str(root / 'tmp/cloudflare-cli.cjs'), 'd1', 'execute', 'easyfix', '--remote', '--command', 'PRAGMA foreign_key_check', '--json'], capture_output=True, text=True, encoding='utf-8', cwd=root, check=True)
    if json.loads(check.stdout)[0]['results']:
        raise RuntimeError('远程外键检查失败')
    report = {'table_counts_verified': True, 'foreign_keys_verified': True, 'tables': actual}
    (Path(sys.argv[1]).parent / 'remote-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
