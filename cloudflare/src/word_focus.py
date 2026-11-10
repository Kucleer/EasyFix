"""词组重点标注的数据库部分：为复习抽题载入「已牢记的词」和「最近的逐词错误」。"""

import json

from phrase_focus import ERROR_WINDOW, focus_indices, spec_active


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
