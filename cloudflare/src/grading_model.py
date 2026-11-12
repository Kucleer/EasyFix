"""批改识别预批的纯逻辑（不碰数据库和网络），见设计 2026-11-12-grading-recognition-design.md 第 4 节。

批改识别比录入识别简单：卷子是系统出的，每个题号对应哪道题、标准答案是什么都已知，
只需要按题号读出孩子写的答案，再和标准答案比。这里放：
- 题号会不会和纸上对不上的判断；
- 比对提示词；
- 模型输出的清洗（题号必须属于这份卷子、漏掉的补成"拿不准"、多出来的丢掉）。
"""

VERDICTS = ('right', 'wrong', 'unsure')     # 对、错、拿不准
MAX_PAGE_TEXT = 20000      # 一页识别文字最多收多少字（正常一页几千字，超出说明不是正常请求）
QUESTION_CHARS = 200       # 提示词里每道题的题目最多给多少字（够模型认出是哪道题就行）
ANSWER_CHARS = 300         # 提示词里每道题的标准答案最多给多少字
STUDENT_ANSWER_CHARS = 200 # 返回给页面的孩子答案最多多少字
NUMBERING_CHANGED_TEXT = '题号可能和纸上不一致，这份卷子请手动批改'


def numbering_changed(practice):
    """打印后有题被删掉时，手动组的卷子题号会往前挪，和纸上对不上，返回 True。

    考点卷的题号是出卷时写下的（display_order），删题不影响其余题号，返回 False。
    手动组的卷子按剩下的题连续编号，题数比创建时少就说明错开了。
    """
    if practice.get('kind') == 'targeted':
        return False
    total = practice.get('total_questions')
    return isinstance(total, int) and total != len(practice.get('questions') or [])


def _cut(text, limit):
    """把文字压成一行并截到 limit 个字，超出的加省略号。"""
    flat = ' '.join(str(text or '').split())
    return flat if len(flat) <= limit else flat[:limit] + '…'


def build_judge_prompt(subject_name, pages, questions):
    """拼比对提示词。

    pages：[(页号, 识别文字)]，页号从 1 开始，对应家长拍的第几张照片。
    questions：[{'number', 'question_text', 'answer'}]，按卷面题号排好。
    要求模型按题号返回 {"answers": [{"no", "student_answer", "verdict", "page"}]}。
    """
    page_parts = []
    for page_no, text in pages:
        page_parts += ['<<<第 %d 页' % page_no, text or '', '第 %d 页>>>' % page_no, '']
    question_lines = ['%d. 题目：%s\n   标准答案：%s' % (
        q['number'], _cut(q.get('question_text'), QUESTION_CHARS), _cut(q.get('answer'), ANSWER_CHARS))
        for q in questions]
    parts = [
        '你是一位中小学老师，在帮家长批改一份练习卷。卷子上每道题的题号、题目和标准答案都已经给你，'
        '你只需要从照片读出来的文字里找到孩子在每道题上写的最终答案，再和标准答案比对。',
        '学科：%s' % (subject_name or '未知'),
        '',
        '下面是卷子照片逐页读出来的文字（OCR），可能有错字、漏字，题号旁边可能印着"第 N 题"和编号：',
        '',
        *page_parts,
        '下面是这份卷子的全部题目（题号 + 题目开头 + 标准答案）：',
        *question_lines,
        '',
        '请对上面每一道题都给出一项，只返回 JSON：{"answers": [ ... ]}，每项四个字段：',
        '- no：题号（整数，必须是上面列出的题号）。',
        '- student_answer：孩子写的最终答案，原样抄下来；读不到或者空着就写空字符串。',
        '- verdict：right（做对）、wrong（做错）或 unsure（拿不准）。',
        '- page：这道题在第几页（整数），找不到写 null。',
        '',
        '判断规则：',
        '1. 只看最终答案：过程写得乱、有涂改、有笔误，只要最终答案和标准答案一致（或等价），就是 right。',
        '2. 书写形式不同不算错，例如 0.5 和 1/2、化简前后的同一个数。',
        '3. 最终答案读得出、和标准答案不一致：wrong。',
        '4. 读不到孩子的答案、空着没写、或者不确定读对了：unsure，不许猜孩子写了什么。',
        '5. 作图、作文、开放题等没法直接比的：unsure。',
        '6. 选择题按选项字母比；填空题有多个空的，每个空都对才算 right。',
        '',
        '不要输出 JSON 以外的任何内容。数学公式照原样写，JSON 字符串里的每个反斜杠都要写成两个。',
    ]
    return '\n'.join(parts)


def _plain_int(value):
    """整数或纯数字字符串转成整数，其它返回 None（布尔值不算整数）。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def clean_judgement(raw, numbers, page_numbers):
    """清洗模型的比对结果。

    raw：模型返回的 JSON；numbers：{卷面题号: 题目行编号}；page_numbers：这次读出来的页号集合。
    返回按题号排好的列表，每道题一项：{'id', 'number', 'student_answer', 'verdict', 'page'}。
    题号不属于这份卷子的丢掉；同一题号出现多次只认第一次；漏掉的补成"拿不准"；
    判定不是 right / wrong / unsure 的按"拿不准"；页号不是这次读出来的页就当作不知道；
    读不到孩子答案却判了对错的，也改成"拿不准"。
    """
    answers = raw.get('answers') if isinstance(raw, dict) else None
    picked = {}
    for entry in answers if isinstance(answers, list) else []:
        if not isinstance(entry, dict):
            continue
        number = _plain_int(entry.get('no'))
        if number not in numbers or number in picked:
            continue
        student = entry.get('student_answer')
        student = _cut(student, STUDENT_ANSWER_CHARS) if isinstance(student, (str, int, float)) and \
            not isinstance(student, bool) else ''
        verdict = entry.get('verdict') if entry.get('verdict') in VERDICTS else 'unsure'
        if not student:
            verdict = 'unsure'
        page = _plain_int(entry.get('page'))
        picked[number] = {'student_answer': student, 'verdict': verdict,
                          'page': page if page in page_numbers else None}
    result = []
    for number in sorted(numbers):
        item = picked.get(number, {'student_answer': '', 'verdict': 'unsure', 'page': None})
        result.append({'id': numbers[number], 'number': number, **item})
    return result
