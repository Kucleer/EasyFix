"""词组重点标注的数据库部分：为复习抽题载入「已牢记的词」和「最近的逐词错误」。"""

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request

from database import Database
from phrase_focus import ERROR_WINDOW, apply_annotation, focus_indices, spec_active
from prompts import PromptLibrary
from settings import generate_json, load

router = APIRouter()

# 每次标注请求最多处理的词条数（一次请求只调用一次模型）
MAX_ANNOTATE_WORDS = 20


async def load_focus_context(db, rows):
    """为已标注生效的词组计算重点下标，返回 {word_id: {'spec': 标注, 'focus': 重点下标列表}}。

    一次调用恰好两次查询（批量，不按词查询）：
    1. 所有已标注词组用到的 lemma 中，哪些单词已经「牢记」；
    2. 每个词组在当前标注之后、最近 ERROR_WINDOW 次默写的逐词结果。
    没有已标注词组时一次查询都不做。
    """
    # 只处理标注生效的词组，标注解析一次后复用
    specs = {}
    for row in rows:
        if spec_active(row):
            specs[row['id']] = json.loads(row['focus_spec'])
    if not specs:
        return {}

    # 查询一：收集全部实义词 lemma，一次查出其中已牢记的单词
    lemmas = sorted({
        token['lemma']
        for spec in specs.values()
        for token in spec['tokens']
        if token.get('role') == 'content' and token.get('lemma')
    })
    mastered_rows = await db.all(
        "SELECT DISTINCT lower(english) AS lemma FROM word "
        "WHERE entry_type='word' AND deleted=0 AND learning_phase='牢记' "
        "AND lower(english) IN (SELECT value FROM json_each(?))",
        (json.dumps(lemmas, ensure_ascii=False),),
    )
    mastered = {row['lemma'] for row in mastered_rows}

    # 查询二：用窗口函数取每个词组最新的 ERROR_WINDOW 条默写日志。
    # 只看 review_type=1 且带逐词结果、并且不早于当前标注写入时间的日志；
    # 标注时间为空（旧数据）时不设下限。
    log_rows = await db.all(
        "SELECT word_id,token_results FROM ("
        "SELECT l.word_id,l.token_results,"
        "ROW_NUMBER() OVER(PARTITION BY l.word_id ORDER BY l.reviewed_at DESC,l.id DESC) AS rn "
        "FROM word_review_log l JOIN word w ON w.id=l.word_id "
        "WHERE l.deleted=0 AND l.review_type=1 AND l.token_results IS NOT NULL "
        "AND w.id IN (SELECT value FROM json_each(?)) "
        "AND (w.focus_updated_at IS NULL OR l.reviewed_at>=w.focus_updated_at)"
        ") WHERE rn<=? ORDER BY word_id,rn",
        (json.dumps(sorted(specs)), ERROR_WINDOW),
    )
    recent = {}
    for row in log_rows:
        try:
            parsed = json.loads(row['token_results'])
        except ValueError:
            continue  # 损坏的记录忽略
        if isinstance(parsed, list):
            recent.setdefault(row['word_id'], []).append(
                [item for item in parsed if isinstance(item, dict)]
            )

    context = {}
    for word_id, spec in specs.items():
        context[word_id] = {
            'spec': spec,
            'focus': focus_indices(spec, mastered, recent.get(word_id, [])),
        }
    return context


def collect_candidate_lemmas(llm_output):
    """从模型输出中取出所有实义词 lemma（小写去空白），用于一次性查询已有单词。"""
    lemmas = set()
    items = llm_output.get('items') if isinstance(llm_output, dict) else None
    if not isinstance(items, list):
        return []
    for item in items:
        tokens = item.get('tokens') if isinstance(item, dict) else None
        if not isinstance(tokens, list):
            continue
        for token in tokens:
            lemma = token.get('lemma') if isinstance(token, dict) else None
            if isinstance(lemma, str) and lemma.strip():
                lemmas.add(lemma.strip().lower())
    return sorted(lemmas)


async def annotate_words(db, word_ids, generate, default_grade):
    """用模型为一批词组生成草稿标注，返回 {annotated, skipped, failures, missing_lemmas}。

    固定的数据库调用：取词 1 次；有待标注词组时再取已有单词 1 次、批量写入 1 次。
    全部被跳过时不调用模型。已确认的标注永远不会被覆盖。
    """
    rows = await db.all(
        "SELECT id,english,chinese,grade,semester,entry_type,focus_status FROM word "
        "WHERE deleted=0 AND id IN (SELECT value FROM json_each(?))",
        (json.dumps(list(word_ids)),),
    )
    found = {row['id']: row for row in rows}

    skipped = []
    pending = []
    # 按请求顺序处理，保证提示词与响应顺序稳定
    for word_id in word_ids:
        row = found.get(word_id)
        if row is None:
            skipped.append({'id': word_id, 'reason': '词条不存在'})
        elif row['entry_type'] != 'phrase':
            skipped.append({'id': word_id, 'reason': '不是词组'})
        elif row['focus_status'] == 'confirmed':
            skipped.append({'id': word_id, 'reason': '已确认，不覆盖'})
        else:
            pending.append(row)
    if not pending:
        return {'annotated': 0, 'skipped': skipped, 'failures': [], 'missing_lemmas': []}

    prompt = PromptLibrary()._build_phrase_focus_prompt(
        [
            {'id': row['id'], 'english': row['english'], 'chinese': row['chinese'], 'grade': row['grade']}
            for row in pending
        ],
        default_grade,
    )
    llm_output = await generate(prompt)

    # 一次查询取出模型提到的 lemma 中单词本已有的单词
    candidates = collect_candidate_lemmas(llm_output)
    known_words = set()
    if candidates:
        known_rows = await db.all(
            "SELECT DISTINCT lower(english) AS lemma FROM word "
            "WHERE entry_type='word' AND deleted=0 "
            "AND lower(english) IN (SELECT value FROM json_each(?))",
            (json.dumps(candidates, ensure_ascii=False),),
        )
        known_words = {row['lemma'] for row in known_rows}

    result = apply_annotation(pending, llm_output, known_words)
    if result['updates']:
        # 北京时间，格式与 words.save 写入的 focus_updated_at 一致
        stamp = (datetime.utcnow() + timedelta(hours=8)).isoformat(' ')
        # 状态保护：模型调用期间被确认的词条不会被覆盖；复习数据列一概不碰
        statements = [
            (
                "UPDATE word SET focus_spec=?,focus_status='draft',focus_updated_at=? "
                "WHERE id=? AND deleted=0 AND focus_status<>'confirmed'",
                (json.dumps(update['focus_spec'], ensure_ascii=False), stamp, update['id']),
            )
            for update in result['updates']
        ]
        await db.batch(statements)
    return {
        'annotated': len(result['updates']),
        'skipped': skipped,
        'failures': result['failures'],
        'missing_lemmas': result['missing_lemmas'],
    }


@router.post('/api/words/focus/annotate')
async def annotate_route(request: Request):
    """为 1 到 20 个词组生成草稿标注（不覆盖已确认的标注）。"""
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, '请求体必须是 JSON')
    word_ids = payload.get('word_ids') if isinstance(payload, dict) else None
    # 必须是 1 到 20 个互不相同的整数（布尔不算整数）
    if (
        not isinstance(word_ids, list)
        or not 1 <= len(word_ids) <= MAX_ANNOTATE_WORDS
        or any(type(word_id) is not int for word_id in word_ids)
        or len(set(word_ids)) != len(word_ids)
    ):
        raise HTTPException(422, 'word_ids 必须是 1 到 20 个互不相同的整数')
    db = Database(request.scope['env'].DB)
    app_config = await load(request, 'app')
    return await annotate_words(
        db,
        word_ids,
        lambda prompt: generate_json(request, prompt),
        app_config.get('default_grade'),
    )
