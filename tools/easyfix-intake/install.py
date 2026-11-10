"""EasyFix 录入技能的安装脚本：把技能文件装到用户级技能目录，并准备配置文件。

直接运行时以当前用户主目录为 home，从脚本所在目录取技能文件，把每条中文说明
逐行打印出来。只用 Python 标准库；可重复运行，不覆盖已填好的访问口令。
"""
import json
import pathlib
import shutil
import sys

POINTER_MARK = '<!-- easyfix-intake -->'
SKILL_FILES = ('SKILL.md', 'payload-format.md', 'easyfix_intake.py')
DEFAULT_BASE_URL = 'https://easyfix-bl2.pages.dev'
# Claude 读第一个，Codex 等其他工具读第二个
SKILL_DIRS = ('.claude/skills/easyfix-intake', '.agents/skills/easyfix-intake')
CODEX_POINTER_TEXT = ('用户要求把错题或卷子照片录入 EasyFix 时，'
                      '先读 `~/.agents/skills/easyfix-intake/SKILL.md` 并照做。')


def copy_skill_files(home, source):
    """把三个技能文件复制到两个用户级技能目录，覆盖旧文件；返回中文说明列表。"""
    notes = []
    for relative in SKILL_DIRS:
        target = home / relative
        target.mkdir(parents=True, exist_ok=True)
        for name in SKILL_FILES:
            shutil.copyfile(source / name, target / name)
        notes.append('已把技能文件复制到 %s' % target)
    return notes


def ensure_config(home):
    """配置文件不存在时创建（口令留空），已存在时不动；返回 (中文说明, 口令是否为空)。"""
    config_dir = home / '.easyfix'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'intake.json'
    if config_path.exists():
        note = '配置文件已存在，未改动：%s' % config_path
    else:
        config_path.write_text(
            json.dumps({'base_url': DEFAULT_BASE_URL, 'token': ''}, ensure_ascii=False, indent=2),
            encoding='utf-8')
        note = '已创建配置文件：%s' % config_path
    # 只判断口令是否为空，绝不把口令的内容读出来或放进返回的说明里
    token_empty = True
    try:
        data = json.loads(config_path.read_text(encoding='utf-8'))
        token_empty = not (isinstance(data, dict) and str(data.get('token') or ''))
    except (OSError, ValueError):
        token_empty = True
    return note, token_empty


def ensure_codex_pointer(home):
    """在 ~/.codex/AGENTS.md 末尾追加一段指向技能的说明；已有标记时不重复。返回中文说明。"""
    codex_dir = home / '.codex'
    codex_dir.mkdir(parents=True, exist_ok=True)
    pointer_path = codex_dir / 'AGENTS.md'
    existing = pointer_path.read_text(encoding='utf-8') if pointer_path.exists() else ''
    if POINTER_MARK in existing:
        return '%s 已有指向说明，未重复追加' % pointer_path
    # 末尾追加一段，以标记开头；原有内容原样保留，前面补一个空行隔开
    block = POINTER_MARK + '\n' + CODEX_POINTER_TEXT + '\n'
    separator = '' if existing == '' or existing.endswith('\n') else '\n'
    pointer_path.write_text(existing + separator + block, encoding='utf-8')
    return '已在 %s 末尾追加指向技能的说明' % pointer_path


def install(home, source, codex_pointer=False):
    """把技能文件复制到两个用户级技能目录并准备配置文件；返回做了哪些事的中文说明。"""
    notes = copy_skill_files(home, source)
    config_note, token_empty = ensure_config(home)
    notes.append(config_note)
    # 仅当明确要求时才往 Codex 的指向文件里写（Task 0 确认 Codex 不自动读技能目录时才用）
    if codex_pointer:
        notes.append(ensure_codex_pointer(home))
    if token_empty:
        # 口令为空只提醒用户自己去填，不询问、不读取、不打印口令
        notes.append('访问口令还没有填。请打开 %s，把其中的 token 填成 EasyFix 给你的访问口令。'
                     % (home / '.easyfix' / 'intake.json'))
    return notes


def main():
    """直接运行：以当前用户主目录为 home，从脚本所在目录取技能文件，逐行打印说明。"""
    home = pathlib.Path.home()
    source = pathlib.Path(__file__).parent
    for line in install(home, source):
        print(line)
    return 0


if __name__ == '__main__':
    # Windows 上显式按 UTF-8 输出，避免中文乱码
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
