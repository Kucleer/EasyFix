"""词组默写优化的本地测试。

第一部分是纯函数测试（切词、标注校验、重点计算、格子、档位与阶段），
不依赖数据库。后续任务会在本脚本中追加数据库相关测试。运行：

    python cloudflare/scripts/phrase_focus_test.py
"""

import asyncio
import datetime
import json
import pathlib
import sqlite3
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from phrase_focus import (  # noqa: E402
    build_cells,
    entry_type_of,
    focus_indices,
    next_level,
    next_phase,
    normalize_english,
    spec_active,
    split_tokens,
    validate_focus_spec,
)
from fastapi import HTTPException  # noqa: E402
from knowledge_invariants_test import SQLiteDB  # noqa: E402  复用生产异步接口的 sqlite 适配器
import review  # noqa: E402
from analytics import now  # noqa: E402
from review import start_session, submit_session  # noqa: E402
from word_focus import load_focus_context  # noqa: E402
from words import import_words, list_words, save, word_stats  # noqa: E402


def configure_output():
    """把标准输出改成 utf-8，避免 Windows GBK 控制台打印中文时报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def expect_value_error(function):
    """调用函数，要求它必须抛出 ValueError。"""
    try:
        function()
    except ValueError:
        return
    raise AssertionError('期望抛出 ValueError，但没有抛出')


def make_spec(english, token_roles):
    """按 (角色, lemma) 列表构造并校验标注，返回规范化后的 spec。"""
    words = english.split()
    assert len(words) == len(token_roles), '测试夹具的词数与角色数不一致'
    tokens = []
    for text, item in zip(words, token_roles):
        role, lemma = item if isinstance(item, tuple) else (item, None)
        token = {'text': text, 'role': role}
        if lemma is not None:
            token['lemma'] = lemma
        tokens.append(token)
    return validate_focus_spec({'tokens': tokens}, english)


SPEC_GOOD_AT = make_spec('be good at', ['plain', 'plain', 'collocation'])
SPEC_PROUD_OF = make_spec('be proud of', ['plain', ('content', 'proud'), 'collocation'])
SPEC_LOOK_FORWARD = make_spec(
    'look forward to doing sth.',
    ['plain', 'collocation', 'collocation', 'placeholder', 'placeholder'],
)
SPEC_TAKE_PART_IN = make_spec('take part in', ['plain', 'plain', 'collocation'])
SPEC_HELP_WITH = make_spec(
    'help sb. with sth.', ['plain', 'placeholder', 'collocation', 'placeholder']
)
SPEC_A_LOT_OF = make_spec('a lot of', ['plain', 'plain', 'collocation'])
SPEC_ALL_CONTENT = make_spec(
    'make friends', [('content', 'make'), ('content', 'friend')]
)

# ---------------------------------------------------------------- 数据库助手

# 迁移 0010 之前的旧表结构（不含任何新列，新列只能由迁移文件带来）。
# word / practice_set / write_guard / request_record / subject / tag 取自
# knowledge_invariants_test.py 的 SCHEMA；word_review_log、word_review、
# word_review_session 取自 backend/app/models/word.py 与 practice_set.py，
# word_tag 取自 backend 的关联表定义加 0003 迁移追加的 deleted 列。
LEGACY_SCHEMA = """
CREATE TABLE subject (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, deleted BOOLEAN NOT NULL DEFAULT 0);
CREATE TABLE tag (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, color VARCHAR(50), deleted BOOLEAN NOT NULL DEFAULT 0);
CREATE TABLE practice_set (
  id INTEGER NOT NULL, name VARCHAR(200) NOT NULL, notes TEXT, subject_id INTEGER NOT NULL,
  source_type VARCHAR(20), question_type VARCHAR(20), pdf_path VARCHAR(500), total_questions INTEGER,
  reviewed BOOLEAN, review_count INTEGER, accuracy DOUBLE PRECISION, last_reviewed_at TIMESTAMP,
  review_images TEXT, passage_id INTEGER, deleted BOOLEAN NOT NULL, created_at TIMESTAMP,
  CONSTRAINT practice_set_pkey PRIMARY KEY (id));
CREATE TABLE request_record (name TEXT PRIMARY KEY, value TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE write_guard (id INTEGER PRIMARY KEY CHECK (id=1), revision INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE word (
  id INTEGER PRIMARY KEY, english VARCHAR(200) NOT NULL, chinese VARCHAR(500), phonetic VARCHAR(200),
  grade INTEGER, semester INTEGER, review_count INTEGER NOT NULL DEFAULT 0,
  correct_count INTEGER NOT NULL DEFAULT 0, ease_factor DOUBLE PRECISION, interval INTEGER,
  learning_phase VARCHAR(20), next_review_at TIMESTAMP, last_reviewed_at TIMESTAMP,
  deleted BOOLEAN NOT NULL DEFAULT 0, created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE TABLE word_tag (
  word_id INTEGER NOT NULL, tag_id INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (word_id, tag_id));
CREATE TABLE word_review_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER NOT NULL, is_correct BOOLEAN NOT NULL,
  user_answer TEXT, review_type INTEGER NOT NULL, reviewed_at TIMESTAMP NOT NULL,
  deleted BOOLEAN NOT NULL DEFAULT 0);
CREATE TABLE word_review (
  id INTEGER PRIMARY KEY AUTOINCREMENT, total_count INTEGER DEFAULT 0, correct_count INTEGER DEFAULT 0,
  error_count INTEGER DEFAULT 0, duration INTEGER DEFAULT 0, reviewed_at TIMESTAMP NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE word_review_session (
  id INTEGER PRIMARY KEY AUTOINCREMENT, practice_set_id INTEGER, session_id INTEGER NOT NULL,
  total_count INTEGER DEFAULT 0, correct_count INTEGER DEFAULT 0, accuracy INTEGER DEFAULT 0,
  duration INTEGER DEFAULT 0, reviewed_at TIMESTAMP, word_results TEXT,
  deleted INTEGER NOT NULL DEFAULT 0);
"""

MIGRATION_PATH = ROOT / 'migrations' / '0010_phrase_focus.sql'


def new_connection(check_same_thread=True):
    """创建带 Row 工厂的内存 sqlite 连接。"""
    connection = sqlite3.connect(':memory:', check_same_thread=check_same_thread)
    connection.row_factory = sqlite3.Row
    return connection


def build_legacy_database(check_same_thread=True):
    """建立只有旧表结构的内存库，并放入写入保护行。"""
    connection = new_connection(check_same_thread)
    connection.executescript(LEGACY_SCHEMA)
    connection.execute('INSERT INTO write_guard(id,revision,deleted) VALUES(1,0,0)')
    connection.execute("INSERT INTO subject(id,name,deleted) VALUES(1,'英语',0)")
    connection.commit()
    return connection


def apply_migration(connection):
    """执行 0010 迁移文件。"""
    connection.executescript(MIGRATION_PATH.read_text(encoding='utf-8'))
    connection.commit()


def build_database(check_same_thread=True):
    """旧表结构加 0010 迁移，后续任务的数据库测试都从这里开始。"""
    connection = build_legacy_database(check_same_thread)
    apply_migration(connection)
    return connection


def adapter(connection):
    """把连接包装成生产代码使用的异步数据库接口。"""
    return SQLiteDB(connection)


def run(coroutine):
    """同步运行一个协程。"""
    return asyncio.run(coroutine)


def expect_http(status_code, function):
    """调用函数，要求它抛出指定状态码的 HTTPException。"""
    try:
        function()
    except HTTPException as error:
        assert error.status_code == status_code, '期望 %s，实际 %s' % (status_code, error.status_code)
        return
    raise AssertionError('期望 HTTP %s，但没有抛出' % status_code)


# ---------------------------------------------------------------- 任务 1


def test_tokens_and_type():
    """切词与词条类型判断。"""
    assert normalize_english('  be   good\tat ') == 'be good at'
    assert split_tokens('help sb. with sth.') == ['help', 'sb.', 'with', 'sth.']
    assert entry_type_of('ice-cream') == 'word'
    assert entry_type_of('a.m.') == 'word'
    assert entry_type_of(' apple ') == 'word'
    assert entry_type_of('be good at') == 'phrase'


def test_validate_focus_spec():
    """标注校验：规范化通过，非法输入抛 ValueError。"""
    spec = {
        'tokens': [
            {'text': 'be', 'role': 'plain'},
            {'text': 'proud', 'role': 'content', 'lemma': 'Proud', 'gloss': '自豪的'},
            {'text': 'of', 'role': 'collocation'},
            {'text': 'sb.', 'role': 'placeholder'},
        ]
    }
    result = validate_focus_spec(spec, ' be  proud of sb. ')
    assert result['version'] == 1
    assert result['source_english'] == 'be proud of sb.'
    assert result['tokens'][1] == {
        'text': 'proud',
        'role': 'content',
        'lemma': 'proud',
        'gloss': '自豪的',
    }
    # 非 content 不保留 lemma/gloss
    assert set(result['tokens'][0]) == {'text', 'role'}
    bad_specs = (
        {'tokens': spec['tokens'][:3]},  # 少一个 token
        {'tokens': [{**spec['tokens'][0], 'text': 'is'}, *spec['tokens'][1:]]},  # 改写了词
        {'tokens': [{**spec['tokens'][0], 'role': 'verb'}, *spec['tokens'][1:]]},  # 非法角色
        {
            'tokens': [
                spec['tokens'][0],
                {'text': 'proud', 'role': 'content'},
                *spec['tokens'][2:],
            ]
        },  # content 无 lemma
        {'tokens': 'x'},
        None,
        [],
    )
    for bad in bad_specs:
        expect_value_error(lambda bad=bad: validate_focus_spec(bad, 'be proud of sb.'))


def test_spec_active():
    """标注是否生效：状态、可解析、与当前英文一致。"""
    spec = json.dumps(validate_focus_spec(SPEC_GOOD_AT, 'be good at'))
    assert spec_active({'english': 'be  good at', 'focus_status': 'draft', 'focus_spec': spec})
    assert spec_active({'english': 'be good at', 'focus_status': 'confirmed', 'focus_spec': spec})
    assert not spec_active({'english': 'be good at', 'focus_status': 'none', 'focus_spec': spec})
    assert not spec_active({'english': 'be good in', 'focus_status': 'confirmed', 'focus_spec': spec})
    assert not spec_active({'english': 'be good at', 'focus_status': 'draft', 'focus_spec': '{bad'})
    assert not spec_active({'english': 'be good at', 'focus_status': 'draft', 'focus_spec': None})


# ---------------------------------------------------------------- 任务 2


def cloze(spec, stored, requested=None, mastered=(), recent=()):
    """把格子渲染成设计文档第 7 节的显示形式，便于断言。"""
    focus = focus_indices(spec, set(mastered), list(recent))
    tokens, level = build_cells(spec, stored, requested, focus)
    parts = []
    for token in tokens:
        if token['blank']:
            # 空出的词：先显示提示（如有），其余字符用下划线
            hint = token['hint'] or ''
            parts.append(hint + '_' * (len(token['text']) - len(hint)))
        else:
            parts.append(token['text'])
    return ' '.join(parts), level


def test_spec_examples():
    """设计文档中的档位 1 示例。"""
    assert cloze(SPEC_GOOD_AT, 1) == ('be good __', 1)
    assert cloze(SPEC_PROUD_OF, 1) == ('be _____ __', 1)
    assert cloze(SPEC_PROUD_OF, 1, mastered={'proud'}) == ('be proud __', 1)
    assert cloze(SPEC_LOOK_FORWARD, 1) == ('look _______ __ doing sth.', 1)
    assert cloze(SPEC_TAKE_PART_IN, 1) == ('take part __', 1)
    assert cloze(SPEC_HELP_WITH, 1) == ('help sb. ____ sth.', 1)


def test_levels_two_and_three():
    """档位 2 给首字母提示，档位 3 全空（占位符除外）。"""
    assert cloze(SPEC_HELP_WITH, 2) == ('h___ sb. w___ sth.', 2)
    assert cloze(SPEC_HELP_WITH, 3) == ('____ sb. ____ sth.', 3)
    assert cloze(SPEC_HELP_WITH, 1, requested=3) == ('____ sb. ____ sth.', 3)  # 手动选档
    assert cloze(SPEC_A_LOT_OF, 2) == ('a l__ o_', 2)  # 单字母 token 在档位 2 不空


def test_empty_focus_falls_back_to_full():
    """无搭配词且实义词全已掌握时，本次按档位 3。"""
    assert cloze(SPEC_ALL_CONTENT, 1, mastered={'make', 'friend'}) == ('____ _______', 3)


def test_error_driven_focus():
    """最近错误次数达到阈值的词加入重点，占位符除外。"""
    wrong_good = [{'i': 1, 'ok': False}, {'i': 2, 'ok': True}]
    assert focus_indices(SPEC_GOOD_AT, set(), [wrong_good]) == [2]  # 错 1 次不够
    assert focus_indices(SPEC_GOOD_AT, set(), [wrong_good, wrong_good]) == [1, 2]
    wrong_sb = [{'i': 1, 'ok': False}]
    assert focus_indices(SPEC_HELP_WITH, set(), [wrong_sb, wrong_sb]) == [2]  # 占位符不会被加入


def test_next_level():
    """档位只在已标注的默写题中升降。"""
    assert next_level(1, True, 1, True) == 2
    assert next_level(3, True, 1, True) == 3
    assert next_level(2, False, 1, True) == 1
    assert next_level(1, False, 1, True) == 1
    assert next_level(2, True, 2, True) == 2  # 选择题不改档位
    assert next_level(2, True, 3, True) == 2  # 听力不改档位
    assert next_level(1, True, 1, False) == 1  # 未标注不改


def test_next_phase():
    """“牢记”阶段规则。"""
    args = dict(consecutive=3, interval=8, was_due=False)
    # 未标注或单词：与旧公式一致
    assert next_phase('在途', True, annotated=False, review_type=2, level=3, **args) == '牢记'
    assert next_phase('牢记', True, consecutive=1, interval=8, was_due=True, annotated=False, review_type=1, level=3) == '遗忘点'
    assert next_phase('牢记', False, annotated=False, review_type=1, level=3, **args) == '在途'
    # 已标注：只在档位 3 的默写授予
    assert next_phase('在途', True, annotated=True, review_type=1, level=3, **args) == '牢记'
    assert next_phase('在途', True, annotated=True, review_type=1, level=1, **args) == '在途'
    assert next_phase('在途', True, annotated=True, review_type=2, level=3, **args) == '在途'
    assert next_phase('在途', True, annotated=True, review_type=3, level=3, **args) == '在途'
    assert next_phase('在途', True, consecutive=3, interval=8, was_due=True, annotated=True, review_type=1, level=1) == '遗忘点'
    # 已标注且已是牢记：答对即保持
    assert next_phase('牢记', True, consecutive=1, interval=2, was_due=True, annotated=True, review_type=2, level=1) == '牢记'
    assert next_phase('牢记', False, annotated=True, review_type=1, level=3, **args) == '在途'


# ---------------------------------------------------------------- 任务 3


def test_migration_backfill():
    """迁移回填：词组类型与默认档位，原有字段不变。"""
    connection = build_legacy_database()  # 仅旧表结构
    connection.executescript("""
      INSERT INTO word(id,english,chinese,learning_phase,review_count,correct_count,interval,deleted) VALUES
        (1,'apple','苹果','在途',4,3,4,0),
        (2,'be good at','擅长','在途',2,1,2,0),
        (3,'look forward to','期待','牢记',6,6,16,0),
        (4,' ice-cream ','冰淇淋',NULL,0,0,1,0),
        (5,'take part in','参加','新学',0,0,1,1);
    """)
    before = connection.execute('SELECT id,english,chinese,learning_phase,review_count,correct_count,interval,deleted FROM word ORDER BY id').fetchall()
    apply_migration(connection)
    rows = {r['id']: r for r in connection.execute('SELECT * FROM word')}
    assert [rows[i]['entry_type'] for i in (1, 2, 3, 4, 5)] == ['word', 'phrase', 'phrase', 'word', 'phrase']
    assert [rows[i]['dictation_level'] for i in (1, 2, 3, 4, 5)] == [3, 1, 3, 3, 1]
    assert all(rows[i]['focus_status'] == 'none' and rows[i]['focus_spec'] is None for i in rows)
    after = connection.execute('SELECT id,english,chinese,learning_phase,review_count,correct_count,interval,deleted FROM word ORDER BY id').fetchall()
    assert [tuple(r) for r in before] == [tuple(r) for r in after]  # 原有字段不变
    log_columns = {r['name'] for r in connection.execute('PRAGMA table_info(word_review_log)')}
    assert {'token_results', 'dictation_level'} <= log_columns


# ---------------------------------------------------------------- 任务 4

PROUD_OF_TOKENS = [
    {'text': 'be', 'role': 'plain'},
    {'text': 'proud', 'role': 'content', 'lemma': 'proud'},
    {'text': 'of', 'role': 'collocation'},
]
GOOD_AT_TOKENS = [
    {'text': 'be', 'role': 'plain'},
    {'text': 'good', 'role': 'plain'},
    {'text': 'at', 'role': 'collocation'},
]

# 列表与统计测试的夹具：(english, chinese, 复习次数, 正确次数, 标注状态, 是否删除)
LISTING_ROWS = [
    ('apple', '苹果', 0, 0, 'none', 0),
    ('banana', '香蕉', 3, 2, 'none', 0),
    ('be good at', '擅长', 4, 2, 'confirmed', 0),
    ('take part in', '参加', 2, 1, 'draft', 0),
    ('look forward to', '期待', 0, 0, 'none', 0),
    ('a lot of', '许多', 5, 5, 'confirmed', 1),  # 已删除，不参与列表与统计
]
PHRASES = {'be good at', 'take part in', 'look forward to'}
CONFIRMED = {'be good at'}
WORD_TOTAL = 2
PHRASE_TOTAL = 3


def build_listing_database():
    """建库并写入列表与统计夹具，返回异步数据库接口。"""
    connection = build_database()
    for index, (english, chinese, reviews, corrects, status, deleted) in enumerate(LISTING_ROWS, start=1):
        entry_type = 'phrase' if ' ' in english else 'word'
        connection.execute(
            'INSERT INTO word(id,english,chinese,review_count,correct_count,learning_phase,'
            'deleted,created_at,entry_type,focus_status) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (index, english, chinese, reviews, corrects, '新学', deleted,
             '2026-01-01 00:00:0%d' % index, entry_type, status),
        )
    connection.commit()
    return adapter(connection)


def test_save_entry_type_and_focus():
    """保存词条：类型默认值、标注校验、英文改动使标注失效。"""
    db = adapter(build_database())
    created = run(save(db, {'english': 'be  proud of', 'chinese': '为…自豪', 'grade': 6}))
    assert (created['entry_type'], created['focus_status'], created['dictation_level']) == ('phrase', 'none', 1)
    single = run(save(db, {'english': 'proud', 'chinese': '自豪的'}))
    assert (single['entry_type'], single['dictation_level']) == ('word', 3)
    # 带标注保存 → confirmed，并写 focus_updated_at
    saved = run(save(db, {'focus_spec': {'tokens': PROUD_OF_TOKENS}}, created['id']))
    assert saved['focus_status'] == 'confirmed' and saved['focus_spec']['source_english'] == 'be proud of'
    assert saved['focus_updated_at']
    # 普通编辑不改变标注状态
    run(db.run("UPDATE word SET focus_status='draft' WHERE id=?", (created['id'],)))
    assert run(save(db, {'chinese': '以…为荣'}, created['id']))['focus_status'] == 'draft'
    # 英文改动 → 标注失效但保留
    changed = run(save(db, {'english': 'be proud in'}, created['id']))
    assert changed['focus_status'] == 'none' and changed['focus_spec'] is not None
    # 只是空白不同不算改动
    run(save(db, {'focus_spec': {'tokens': [{'text': 'be', 'role': 'plain'}, {'text': 'proud', 'role': 'plain'}, {'text': 'in', 'role': 'collocation'}]}}, created['id']))
    assert run(save(db, {'english': ' be  proud in '}, created['id']))['focus_status'] == 'confirmed'
    # 非法标注 → 422，原记录不变
    expect_http(422, lambda: run(save(db, {'focus_spec': {'tokens': PROUD_OF_TOKENS}}, created['id'])))
    # 手动指定类型
    assert run(save(db, {'entry_type': 'word'}, created['id']))['entry_type'] == 'word'
    expect_http(422, lambda: run(save(db, {'entry_type': 'sentence'}, created['id'])))


def test_batch_import_with_focus():
    """批量导入：标注不符的条目照常导入，只在结果里带 focus_error。"""
    db = adapter(build_database())
    result = run(import_words(db, {'words': [
        {'english': 'be good at', 'chinese': '擅长', 'focus_spec': {'tokens': GOOD_AT_TOKENS}},
        {'english': 'take part in', 'chinese': '参加', 'focus_spec': {'tokens': GOOD_AT_TOKENS}},  # 与英文不符
        {'english': 'apple', 'chinese': '苹果'},
    ]}))
    assert result['success_count'] == 3
    assert 'focus_error' in result['results'][1] and 'focus_error' not in result['results'][0]
    rows = {r['english']: r for r in run(db.all('SELECT * FROM word WHERE deleted=0'))}
    assert (rows['be good at']['focus_status'], rows['take part in']['focus_status'], rows['apple']['entry_type']) == ('confirmed', 'none', 'word')
    assert (rows['be good at']['dictation_level'], rows['apple']['dictation_level']) == (1, 3)
    assert rows['take part in']['focus_spec'] is None


def test_listing_filters_and_stats():
    """列表按类型和标注状态筛选，统计按类型汇总。"""
    db = build_listing_database()
    assert {r['english'] for r in run(list_words(db, {'entry_type': 'phrase'}, 0, 50))['items']} == PHRASES
    assert {r['english'] for r in run(list_words(db, {'focus_status': 'confirmed'}, 0, 50))['items']} == CONFIRMED
    stats = run(word_stats(db))
    assert stats['by_type']['word']['total'] == WORD_TOTAL and stats['by_type']['phrase']['total'] == PHRASE_TOTAL
    assert stats['by_type']['phrase']['accuracy'] == 50.0  # 夹具：词组合计 correct 3 / review 6
    assert stats['by_type']['word']['accuracy'] == round(2 / 3 * 100, 1)
    # 列表返回新增字段，focus_spec 为解析后的对象或 None
    item = run(list_words(db, {'entry_type': 'phrase'}, 0, 50))['items'][0]
    assert {'entry_type', 'focus_status', 'focus_spec', 'dictation_level'} <= set(item)
    assert item['focus_spec'] is None
    # 原有统计字段保持不变
    assert stats['total_words'] == 5


# ---------------------------------------------------------------- 任务 5 的测试助手


class FakeEnv:
    """伪造 Cloudflare 的 env，只带一个 DB 属性。"""

    DB = None


class FakeRequest:
    """伪造 FastAPI 的 Request，只提供 scope 与 json()。"""

    def __init__(self, payload):
        self.scope = {'env': FakeEnv()}
        self.payload = payload

    async def json(self):
        """返回构造时给定的请求体。"""
        return self.payload


def submit_endpoint(db, payload):
    """经由提交端点提交（把 review.Database 换成测试库），返回端点的响应。"""
    original = review.Database
    review.Database = lambda binding: db
    try:
        return run(review.submit(FakeRequest(payload)))
    finally:
        review.Database = original


def stamp_of(moment):
    """按生产代码的格式（isoformat 加空格）生成时间字符串。"""
    return moment.isoformat(' ')


def insert_word(db, english, chinese='释义', phase='在途', reviews=0, corrects=0,
                interval=1, next_review_at=None, level=None, spec=None, status='none',
                focus_updated_at=None):
    """直接插入一个词条，返回 id；类型与默认档位与迁移规则一致。"""
    entry_type = 'phrase' if len(english.split()) > 1 else 'word'
    if level is None:
        level = 1 if entry_type == 'phrase' else 3
    result = run(db.run(
        'INSERT INTO word(english,chinese,review_count,correct_count,interval,learning_phase,'
        'next_review_at,deleted,entry_type,focus_spec,focus_status,focus_updated_at,dictation_level) '
        'VALUES(?,?,?,?,?,?,?,0,?,?,?,?,?)',
        (english, chinese, reviews, corrects, interval, phase, next_review_at, entry_type,
         json.dumps(spec, ensure_ascii=False) if spec else None, status, focus_updated_at, level)))
    return result['last_row_id']


def add_log(db, word_id, ok, review_type=1, reviewed_at='2026-01-02 00:00:00',
            token_results=None, level=None):
    """直接插入一条复习日志（用来构造连续答对等历史）。"""
    run(db.run(
        'INSERT INTO word_review_log(word_id,is_correct,user_answer,review_type,reviewed_at,deleted,'
        'token_results,dictation_level) VALUES(?,?,?,?,?,0,?,?)',
        (word_id, ok, 'x', review_type, reviewed_at,
         json.dumps(token_results) if token_results is not None else None, level)))


def begin(db, only=None):
    """直接登记一个复习场次，返回 (session_id, {english: word_id})。"""
    ids = {row['english']: row['id'] for row in run(db.all('SELECT id,english FROM word WHERE deleted=0'))}
    chosen = [ids[only]] if only else list(ids.values())
    session = run(db.run(
        'INSERT INTO word_review(total_count,correct_count,error_count,duration,reviewed_at) VALUES(?,0,0,0,?)',
        (len(chosen), stamp_of(now()))))['last_row_id']
    run(db.run('INSERT INTO request_record(name,value,deleted,created_at) VALUES(?,?,0,?)',
               ('word-session:%d' % session, json.dumps(chosen), stamp_of(now()))))
    return session, ids


def by_english(db):
    """按英文返回全部词条行。"""
    return {row['english']: row for row in run(db.all('SELECT * FROM word WHERE deleted=0'))}


def latest_log(db, word_id):
    """返回某个词最新的一条日志。"""
    return run(db.first('SELECT * FROM word_review_log WHERE word_id=? ORDER BY id DESC', (word_id,)))


# ---------------------------------------------------------------- 任务 5


def test_legacy_submit_characterization():
    """单词与未标注词组的提交结果（阶段、间隔、计数、日志、下次复习日）与旧实现一致。"""
    db = adapter(build_database())
    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    past = stamp_of(now() - datetime.timedelta(days=1))
    apple = insert_word(db, 'apple', phase='在途', reviews=3, corrects=2, interval=4, next_review_at=past)
    phrase = insert_word(db, 'take part in', phase='牢记', reviews=5, corrects=5, interval=16, next_review_at=past)
    proud = insert_word(db, 'proud', phase='在途', reviews=2, corrects=1, interval=1, next_review_at=past)
    add_log(db, apple, True, reviewed_at='2026-01-01 00:00:01')
    add_log(db, apple, True, reviewed_at='2026-01-01 00:00:02')
    add_log(db, proud, False, reviewed_at='2026-01-01 00:00:03')
    session, ids = begin(db)
    results = [
        {'word_id': apple, 'is_correct': True, 'user_answer': 'apple', 'review_type': 2},
        {'word_id': phrase, 'is_correct': False, 'user_answer': 'take par in', 'review_type': 1},
        {'word_id': proud, 'is_correct': True, 'user_answer': 'proud', 'review_type': 1},
    ]
    payload = {'session_id': session, 'duration': 12, 'results': results}
    out = submit_endpoint(db, payload)
    assert out == {'total': 3, 'correct': 2, 'error': 1, 'accuracy': 66.7}
    words = by_english(db)
    # 连对 3 次且间隔 8 天：牢记（选择题对单词同样适用）
    assert (words['apple']['learning_phase'], words['apple']['interval'], words['apple']['review_count'],
            words['apple']['correct_count']) == ('牢记', 8, 4, 3)
    assert words['apple']['next_review_at'] == stamp_of(today + datetime.timedelta(days=8))
    # 答错：间隔回到 1，阶段回到在途，正确数不变
    assert (words['take part in']['learning_phase'], words['take part in']['interval'],
            words['take part in']['review_count'], words['take part in']['correct_count']) == ('在途', 1, 6, 5)
    assert words['take part in']['next_review_at'] == stamp_of(today + datetime.timedelta(days=1))
    # 到期后答对但连对不足：遗忘点
    assert (words['proud']['learning_phase'], words['proud']['interval']) == ('遗忘点', 2)
    assert words['proud']['next_review_at'] == stamp_of(today + datetime.timedelta(days=2))
    # 单词与未标注词组的档位列不变
    assert (words['apple']['dictation_level'], words['take part in']['dictation_level']) == (3, 1)
    log = latest_log(db, phrase)
    assert (log['is_correct'], log['user_answer'], log['review_type'], log['token_results'],
            log['dictation_level']) == (0, 'take par in', 1, None, None)
    log = latest_log(db, apple)
    assert (log['is_correct'], log['review_type'], log['token_results'], log['dictation_level']) == (1, 2, None, None)
    # 场次、练习集与幂等记录
    session_row = run(db.first('SELECT correct_count,error_count,duration FROM word_review WHERE id=?', (session,)))
    assert session_row == {'correct_count': 2, 'error_count': 1, 'duration': 12}
    assert run(db.first("SELECT COUNT(*) AS n FROM practice_set WHERE source_type='word'"))['n'] == 1
    summary = run(db.first('SELECT total_count,correct_count,accuracy FROM word_review_session'))
    assert summary == {'total_count': 3, 'correct_count': 2, 'accuracy': 66}
    again = submit_endpoint(db, payload)
    assert again == out and by_english(db)['apple']['review_count'] == 4  # 重复提交不再改动


FOCUS_STAMP = '2026-01-01 00:00:00'


def seeded():
    """复习测试夹具：单词 apple、已确认词组、草稿词组、未标注词组、在途单词 proud。"""
    db = adapter(build_database())
    insert_word(db, 'apple', '苹果')
    insert_word(db, 'be good at', '擅长', spec=SPEC_GOOD_AT, status='confirmed', focus_updated_at=FOCUS_STAMP)
    insert_word(db, 'be proud of', '为…自豪', spec=SPEC_PROUD_OF, status='draft', focus_updated_at=FOCUS_STAMP)
    insert_word(db, 'take part in', '参加')
    insert_word(db, 'proud', '自豪的')
    return db


def counted_queries(db, coroutine_factory):
    """运行协程，返回适配器上 first/all/run/batch 的调用总次数。"""
    calls = []
    names = ('first', 'all', 'run', 'batch')
    originals = {name: getattr(db, name) for name in names}

    def wrap(name):
        """包一层计数，再转发给原方法。"""
        async def counted(*args, **kwargs):
            calls.append(name)
            return await originals[name](*args, **kwargs)
        return counted

    for name in names:
        setattr(db, name, wrap(name))
    try:
        run(coroutine_factory())
    finally:
        for name in names:
            setattr(db, name, originals[name])
    return len(calls)


def baseline_start_queries():
    """同一份数据在没有任何已标注词组时，start_session 的数据库调用次数。"""
    db = seeded()
    run(db.run("UPDATE word SET focus_status='none'"))
    return counted_queries(db, lambda: start_session(db, 10, None, None, None, None))


BASELINE_START_QUERIES = baseline_start_queries()


def one_correct_payload(session, ids, level):
    """只含「be good at」一条答对默写结果的提交内容。"""
    return {'session_id': session, 'duration': 5, 'results': [
        {'word_id': ids['be good at'], 'is_correct': True, 'user_answer': 'be good at',
         'review_type': 1, 'dictation_level': level, 'token_results': [{'i': 2, 'ok': True}]}]}


def test_start_returns_tokens():
    """抽题：已标注词组带格子，单词与未标注词组不带；只多两次查询。"""
    db = seeded()
    data = run(start_session(db, 10, None, None, None, None))
    by = {q['english']: q for q in data['questions']}
    assert 'tokens' not in by['apple'] and by['apple']['dictation_level'] == 3
    assert 'tokens' not in by['take part in'] and by['take part in']['dictation_level'] == 3
    assert [t['blank'] for t in by['be good at']['tokens']] == [False, False, True]
    assert [t['blank'] for t in by['be proud of']['tokens']] == [False, True, True]  # proud 未牢记
    assert by['apple']['entry_type'] == 'word' and by['be good at']['entry_type'] == 'phrase'
    run(db.run("UPDATE word SET learning_phase='牢记' WHERE english='proud'"))
    data = run(start_session(db, 10, None, None, 'phrase', None))
    by = {q['english']: q for q in data['questions']}
    assert set(by) == {'be good at', 'be proud of', 'take part in'}
    assert [t['blank'] for t in by['be proud of']['tokens']] == [False, False, True]
    data = run(start_session(db, 10, None, None, 'phrase', 3))
    assert all(t['blank'] for t in {q['english']: q for q in data['questions']}['be good at']['tokens'])
    assert counted_queries(db, lambda: start_session(db, 10, None, None, None, None)) <= BASELINE_START_QUERIES + 2


def test_start_without_annotation_adds_no_queries():
    """没有已标注词组时，抽题的数据库调用次数与旧实现一致（3 次）。"""
    db = seeded()
    run(db.run("UPDATE word SET focus_status='none'"))
    assert BASELINE_START_QUERIES == 3
    assert counted_queries(db, lambda: start_session(db, 10, None, None, None, None)) == 3
    data = run(start_session(db, 10, None, None, None, None))
    assert all('tokens' not in q for q in data['questions'])
    assert {q['entry_type'] for q in data['questions']} == {'word', 'phrase'}


def test_submit_levels_and_logs():
    """提交：已标注词组升降档并记录逐词结果，其余词条的档位列与日志列不变。"""
    db = seeded()
    session, ids = begin(db)
    out, first = run(submit_session(db, {'session_id': session, 'duration': 30, 'results': [
        {'word_id': ids['be good at'], 'is_correct': True, 'user_answer': 'be good at', 'review_type': 1,
         'dictation_level': 1, 'token_results': [{'i': 2, 'ok': True}]},
        {'word_id': ids['be proud of'], 'is_correct': False, 'user_answer': 'be pruod of', 'review_type': 1,
         'dictation_level': 1, 'token_results': [{'i': 1, 'ok': False}, {'i': 2, 'ok': True}]},
        {'word_id': ids['apple'], 'is_correct': True, 'user_answer': 'apple', 'review_type': 1},
        {'word_id': ids['take part in'], 'is_correct': True, 'user_answer': 'take part in', 'review_type': 1},
        {'word_id': ids['proud'], 'is_correct': True, 'user_answer': 'proud', 'review_type': 1}]}))
    assert first and out == {'total': 5, 'correct': 4, 'error': 1, 'accuracy': 80.0}
    words = by_english(db)
    assert words['be good at']['dictation_level'] == 2
    assert words['be proud of']['dictation_level'] == 1
    assert words['apple']['dictation_level'] == 3 and words['take part in']['dictation_level'] == 1  # 未标注：列值不动
    log = latest_log(db, ids['be proud of'])
    assert json.loads(log['token_results']) == [{'i': 1, 'ok': False}, {'i': 2, 'ok': True}] and log['dictation_level'] == 1
    assert latest_log(db, ids['apple'])['token_results'] is None
    assert latest_log(db, ids['apple'])['dictation_level'] is None
    assert latest_log(db, ids['take part in'])['dictation_level'] is None  # 未标注词组不写日志档位


def test_submit_idempotent_keeps_level():
    """重复提交相同内容：返回既有结果，档位与日志都不再变化。"""
    db = seeded()
    session, ids = begin(db, only='be good at')  # 场次只登记提交的那一个词
    payload = one_correct_payload(session, ids, level=1)
    run(submit_session(db, payload))
    out, first = run(submit_session(db, payload))
    assert not first and by_english(db)['be good at']['dictation_level'] == 2
    assert run(db.first('SELECT COUNT(*) AS n FROM word_review_log WHERE word_id=?', (ids['be good at'],)))['n'] == 1


def test_submit_from_old_frontend():
    """旧前端不带新字段：日志记档位 3、无逐词结果，档位照常升一档。"""
    db = seeded()
    session, ids = begin(db, only='be good at')
    out, _ = run(submit_session(db, {'session_id': session, 'duration': 5, 'results': [
        {'word_id': ids['be good at'], 'is_correct': True, 'user_answer': 'be good at', 'review_type': 1}]}))
    assert out['correct'] == 1
    log = latest_log(db, ids['be good at'])
    assert log['dictation_level'] == 3 and log['token_results'] is None
    assert by_english(db)['be good at']['dictation_level'] == 2


def test_manual_level_not_written_back():
    """手动选档不写回词条，但日志记录实际档位。"""
    db = seeded()
    session, ids = begin(db, only='be good at')
    run(submit_session(db, {'session_id': session, 'duration': 5, 'results': [
        {'word_id': ids['be good at'], 'is_correct': True, 'user_answer': 'be good at', 'review_type': 1,
         'dictation_level': 3, 'dictation_auto': False,
         'token_results': [{'i': 0, 'ok': True}, {'i': 1, 'ok': True}, {'i': 2, 'ok': True}]}]}))
    assert by_english(db)['be good at']['dictation_level'] == 1  # 手动选档不写回
    assert latest_log(db, ids['be good at'])['dictation_level'] == 3  # 但日志记实际档位


def grant_case(english, review_type, level, phase='在途', annotated=True, ok=True):
    """构造「连续答对 3 次、间隔够长、未到期」的词条，提交一次后返回词条行。"""
    db = adapter(build_database())
    spec = SPEC_GOOD_AT if annotated else None
    future = stamp_of(now() + datetime.timedelta(days=3))
    word_id = insert_word(db, english, phase=phase, reviews=2, corrects=2, interval=4,
                          next_review_at=future, spec=spec, status='confirmed' if annotated else 'none',
                          focus_updated_at=FOCUS_STAMP if annotated else None)
    add_log(db, word_id, True, reviewed_at='2026-01-02 00:00:01')
    add_log(db, word_id, True, reviewed_at='2026-01-02 00:00:02')
    session, _ = begin(db)
    result = {'word_id': word_id, 'is_correct': ok, 'user_answer': english, 'review_type': review_type}
    if annotated and review_type == 1:
        result['dictation_level'] = level
        result['token_results'] = [{'i': 2, 'ok': ok}]
    out, first = run(submit_session(db, {'session_id': session, 'duration': 5, 'results': [result]}))
    assert first and out['total'] == 1
    return by_english(db)[english]


def test_listening_accepted_and_grant_rules():
    """听力题不再 422；已标注词组只有档位 3 的默写才授予「牢记」。"""
    # 已标注词组：连续 3 次答对且间隔 8 天，档位 1 → 不授予；档位 3 → 授予
    low = grant_case('be good at', 1, 1)
    assert low['learning_phase'] == '在途' and low['interval'] == 8
    high = grant_case('be good at', 1, 3)
    assert high['learning_phase'] == '牢记' and high['interval'] == 8 and high['dictation_level'] == 2  # 档位列从 1 升到 2
    # 听力与选择题不授予，也不改档位
    listening = grant_case('be good at', 3, 3)
    assert listening['learning_phase'] == '在途' and listening['dictation_level'] == 1
    assert listening['review_count'] == 3 and listening['correct_count'] == 3
    choice = grant_case('be good at', 2, 3)
    assert choice['learning_phase'] == '在途' and choice['dictation_level'] == 1
    # 已是「牢记」的已标注词组用选择题答对 → 仍为「牢记」
    kept = grant_case('be good at', 2, 3, phase='牢记')
    assert kept['learning_phase'] == '牢记'
    # 已是「牢记」的已标注词组答错 → 回到在途
    lost = grant_case('be good at', 1, 3, phase='牢记', ok=False)
    assert lost['learning_phase'] == '在途' and lost['interval'] == 1
    # 单词：同样条件用选择题或听力 → 牢记（与旧行为一致）
    assert grant_case('apple', 2, 3, annotated=False)['learning_phase'] == '牢记'
    assert grant_case('apple', 3, 3, annotated=False)['learning_phase'] == '牢记'
    # 未标注词组同样沿用旧公式
    assert grant_case('take part in', 2, 3, annotated=False)['learning_phase'] == '牢记'
    # 听力日志记录题型 3
    db = seeded()
    session, ids = begin(db, only='apple')
    run(submit_session(db, {'session_id': session, 'duration': 5, 'results': [
        {'word_id': ids['apple'], 'is_correct': True, 'user_answer': '', 'review_type': 3}]}))
    assert latest_log(db, ids['apple'])['review_type'] == 3


def test_submit_validation():
    """新字段的形状与取值范围校验，非法一律 422 且不写任何数据。"""
    db = seeded()
    session, ids = begin(db, only='be good at')
    base = {'word_id': ids['be good at'], 'is_correct': True, 'user_answer': 'be good at', 'review_type': 1}
    bad_extras = [
        {'token_results': 'x'},  # 不是列表
        {'token_results': {'i': 1, 'ok': True}},  # 是对象不是列表
        {'token_results': [{'i': '1', 'ok': True}]},  # i 不是整数
        {'token_results': [{'i': True, 'ok': True}]},  # 布尔不算整数
        {'token_results': [{'i': 1, 'ok': 'yes'}]},  # ok 不是布尔
        {'token_results': [{'i': 1}]},  # 缺 ok
        {'token_results': ['x']},  # 元素不是对象
        {'dictation_level': 4},
        {'dictation_level': 0},
        {'dictation_level': '1'},
        {'dictation_auto': 'no'},
        {'review_type': 4},
        {'review_type': 0},
    ]
    for extra in bad_extras:
        payload = {'session_id': session, 'duration': 5, 'results': [{**base, **extra}]}
        expect_http(422, lambda payload=payload: run(submit_session(db, payload)))
    assert run(db.first('SELECT COUNT(*) AS n FROM word_review_log'))['n'] == 0
    assert run(db.first("SELECT COUNT(*) AS n FROM request_record WHERE name LIKE 'word-submit:%'"))['n'] == 0
    # 合法的边界值可以通过
    good = {'session_id': session, 'duration': 5, 'results': [
        {**base, 'dictation_level': 2, 'dictation_auto': True, 'token_results': []}]}
    assert run(submit_session(db, good))[1] is True


def test_error_driven_uses_only_current_annotation():
    """错误驱动只统计当前标注之后、带逐词结果的默写日志，且只看最近 5 条。"""
    db = seeded()
    ids = {row['english']: row['id'] for row in run(db.all('SELECT id,english FROM word'))}
    good_at = ids['be good at']
    run(db.run("UPDATE word SET focus_updated_at='2026-03-01 00:00:00' WHERE id=?", (good_at,)))
    wrong = [{'i': 1, 'ok': False}, {'i': 2, 'ok': True}]

    def blanks():
        """重新抽题，返回「be good at」各格子是否空出。"""
        data = run(start_session(db, 10, None, None, None, None))
        by = {q['english']: q for q in data['questions']}
        return [t['blank'] for t in by['be good at']['tokens']]

    # 标注之前的日志不计入
    add_log(db, good_at, False, reviewed_at='2026-02-01 00:00:00', token_results=wrong)
    add_log(db, good_at, False, reviewed_at='2026-02-02 00:00:00', token_results=wrong)
    assert blanks() == [False, False, True]
    # 标注之后但没有逐词结果的日志不计入；非默写题型也不计入
    add_log(db, good_at, False, reviewed_at='2026-03-02 00:00:00')
    add_log(db, good_at, False, reviewed_at='2026-03-02 00:00:01')
    add_log(db, good_at, False, review_type=2, reviewed_at='2026-03-02 00:00:02', token_results=wrong)
    add_log(db, good_at, False, review_type=3, reviewed_at='2026-03-02 00:00:03', token_results=wrong)
    assert blanks() == [False, False, True]
    # 标注之后只错 1 次不够
    add_log(db, good_at, False, reviewed_at='2026-03-03 00:00:00', token_results=wrong)
    assert blanks() == [False, False, True]
    # 标注之后错满 2 次 → 「good」加入重点
    add_log(db, good_at, False, reviewed_at='2026-03-03 00:00:01', token_results=wrong)
    assert blanks() == [False, True, True]
    # 已软删除的日志不计入
    run(db.run("UPDATE word_review_log SET deleted=1 WHERE reviewed_at='2026-03-03 00:00:01'"))
    assert blanks() == [False, False, True]
    run(db.run("UPDATE word_review_log SET deleted=0 WHERE reviewed_at='2026-03-03 00:00:01'"))
    assert blanks() == [False, True, True]
    # 只看最近 5 条：之后连续 5 次全对，旧的错误滑出窗口
    right = [{'i': 1, 'ok': True}, {'i': 2, 'ok': True}]
    for second in range(5):
        add_log(db, good_at, True, reviewed_at='2026-03-04 00:00:0%d' % second, token_results=right)
    assert blanks() == [False, False, True]
    # 直接检查载入结果：每个已标注词组一项，单词与未标注词组没有
    rows = run(db.all('SELECT * FROM word WHERE deleted=0'))
    context = run(load_focus_context(db, rows))
    assert set(context) == {good_at, ids['be proud of']}
    assert context[good_at]['focus'] == [2]
    assert context[good_at]['spec']['source_english'] == 'be good at'
    assert counted_queries(db, lambda: load_focus_context(db, rows)) == 2
    assert counted_queries(db, lambda: load_focus_context(db, [r for r in rows if r['english'] == 'apple'])) == 0


TESTS = [
    test_tokens_and_type,
    test_validate_focus_spec,
    test_spec_active,
    test_spec_examples,
    test_levels_two_and_three,
    test_empty_focus_falls_back_to_full,
    test_error_driven_focus,
    test_next_level,
    test_next_phase,
    test_migration_backfill,
    test_save_entry_type_and_focus,
    test_batch_import_with_focus,
    test_listing_filters_and_stats,
    test_legacy_submit_characterization,
    test_start_returns_tokens,
    test_start_without_annotation_adds_no_queries,
    test_submit_levels_and_logs,
    test_submit_idempotent_keeps_level,
    test_submit_from_old_frontend,
    test_manual_level_not_written_back,
    test_listening_accepted_and_grant_rules,
    test_submit_validation,
    test_error_driven_uses_only_current_annotation,
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
