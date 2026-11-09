"""校验并导入本地分级阅读包；默认仅预检，正式入库必须提供已验证备份。"""
import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / 'scripts'))


def validate_pack(path):
    """检查篇数、六年级标记、长度、来源、题目及答案，不连接数据库。"""
    pack = json.loads(path.read_text(encoding='utf-8'))
    if not re.fullmatch(r'[a-z0-9_]{1,24}', pack.get('pack_id', '')):
        raise ValueError('pack_id 必须为不超过24位的小写字母、数字或下划线')
    passages = pack.get('passages', [])
    if not 100 <= len(passages) <= 200:
        raise ValueError('阅读包应包含100至200篇不同短文')
    ids, contents = set(), set()
    for item in passages:
        entry = item.get('id', '')
        if not re.fullmatch(r'[a-z0-9_]{1,20}', entry) or entry in ids:
            raise ValueError(f'无效或重复短文ID: {entry}')
        ids.add(entry)
        content = item.get('content', '').strip()
        fingerprint = hashlib.sha256(content.encode()).hexdigest()
        if fingerprint in contents:
            raise ValueError(f'重复正文: {entry}')
        contents.add(fingerprint)
        count = len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", content))
        if not 100 <= count <= 200:
            raise ValueError(f'{entry}: 词数{count}不在100至200范围')
        if item.get('grade') != 6 or item.get('difficulty') not in (1, 2, 3):
            raise ValueError(f'{entry}: 年级或难度不符合首批标准')
        provenance = item.get('provenance', {})
        if not all(provenance.get(k) for k in ('source_name', 'source_url', 'rights_basis', 'exercise_origin')):
            raise ValueError(f'{entry}: 缺少来源、使用依据或题目编写方式')
        published = date.fromisoformat(provenance.get('published_at', ''))
        if published > date.today():
            raise ValueError(f'{entry}: 发布日期不能在未来')
        if not item.get('title', '').strip() or not item.get('topic', '').strip():
            raise ValueError(f'{entry}: 缺少标题或话题')
        questions = item.get('questions', [])
        if len(questions) != 4:
            raise ValueError(f'{entry}: 必须配4道题')
        for number, q in enumerate(questions, 1):
            options = [q.get('option_' + letter, '').strip() for letter in 'abcd']
            if not all(options) or len(set(options)) != 4 or q.get('correct_answer') not in ('A', 'B', 'C', 'D'):
                raise ValueError(f'{entry} 第{number}题选项或答案无效')
            if not q.get('question_text', '').strip() or not q.get('explanation', '').strip():
                raise ValueError(f'{entry} 第{number}题缺少题干或解析')
            evidence = q.get('evidence', '').strip()
            if not evidence or evidence not in content:
                raise ValueError(f'{entry} 第{number}题缺少可回查的原文依据')
            q['question_number'] = number
        item['word_count'] = count
        item['source'] = pack['pack_id'] + ':' + entry
    return pack


def main():
    """预检阅读包，在单一事务中重复安全地导入并回读，保留所有已有数据。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-dir', type=Path)
    args = parser.parse_args()
    pack = validate_pack(args.pack.resolve())
    print(f"阅读包预检通过：{len(pack['passages'])}篇，每篇4题，来源与答案依据完整")
    if not args.apply:
        return
    if not args.backup_dir:
        raise ValueError('正式入库前必须提供 --backup-dir')
    from backup_data import verify_backup
    backup = args.backup_dir.resolve()
    verify_backup(backup)
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    os.chdir(BACKEND)
    from app.config import get_settings
    from app.database import SessionLocal
    from app.models import ReadingPassage, ReadingQuestion
    settings = get_settings()
    database = manifest['database']
    current_type = settings.DB_TYPE.lower()
    backup_type = database.get('type', '').lower()
    aliases = {'postgresql': 'postgres'}
    if aliases.get(current_type, current_type) != aliases.get(backup_type, backup_type):
        raise ValueError('备份数据库类型与当前连接不一致')
    if current_type == 'sqlite':
        if Path(database.get('source_path', '')).resolve() != Path(settings.DB_PATH).resolve():
            raise ValueError('备份 SQLite 路径与当前连接不一致')
    elif any(str(database.get(key)) != str(value) for key, value in [('database', settings.DB_NAME), ('host', settings.DB_HOST), ('port', settings.DB_PORT)]):
        raise ValueError('备份数据库与当前连接不一致')
    inserted = 0
    with SessionLocal() as db:
        with db.begin():
            if db.bind.dialect.name == 'postgresql':
                from sqlalchemy import text
                db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': 2026110806})
            for item in pack['passages']:
                # 包内来源键同时检查软删除记录，不重新创建用户已删除的文章。
                existing = db.query(ReadingPassage).filter(ReadingPassage.source == item['source']).first()
                if existing:
                    if existing.content != item['content'] or existing.title != item['title']:
                        raise ValueError('同一来源键已有不同内容，不自动覆盖')
                    continue
                row = ReadingPassage(**{key: item[key] for key in ('title', 'content', 'topic', 'grade', 'difficulty', 'word_count', 'source')}, deleted=False)
                db.add(row)
                db.flush()
                for q in item['questions']:
                    db.add(ReadingQuestion(passage_id=row.id, deleted=False, **{key: q[key] for key in ('question_number', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'explanation')}))
                db.flush()
                db.refresh(row)
                if row.content != item['content'] or len(row.questions) != 4:
                    raise ValueError('入库回读失败')
                for actual, expected in zip(sorted(row.questions, key=lambda q: q.question_number), item['questions']):
                    for key in ('question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'explanation'):
                        if getattr(actual, key) != expected[key]:
                            raise ValueError('题目答案回读失败')
                inserted += 1
    print(f'导入完成：新增{inserted}篇；已有内容与历史数据未覆盖')


if __name__ == '__main__':
    main()
