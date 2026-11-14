"""整页识别录入的纯逻辑（不碰数据库和网络）。

识别流程（读图 → 整理 → 需要时重扫一次 → 再整理）的先后顺序和判断也写在这里：
后端每个请求只做其中一步（step_read / step_analyze / step_rescan），
回归脚本用 run_page 一口气走完；两边用的是同一套步骤函数，读图和调模型由外面传进来。
本模块只用标准库，主机上的回归脚本可以直接导入。
"""

import json
import re
import time

CONTRACT_VERSION = 1
HEALTH_TIMEOUT_SECONDS = 3

# ---------------------------------------------------------------- 常量

VERDICTS = ('wrong', 'right', 'unsure')
# 读图异常标记 -> 页面上显示的提示文字（设计 6.4）
FLAGS = {
    'broken_formula': '公式可能读错，请对照原图',
    'unsolvable': '题干可能缺内容，请对照原图',
    'merged': '可能串题，请对照原图',
    'figure_needed': '这题有图，请对照原图补条件',
}
ITEM_STATES = ('open', 'accepted', 'dismissed')
# 几个时限的关系（设计第 7 节）：主机单次最多 110 秒 < 后端调主机 120 秒、调模型 120 秒
# < 页面等一步 150 秒 < 判定卡住 180 秒，正常的慢步骤不会被误判成卡住
STALE_SECONDS = 180          # 一步超过这么久没结束，视为卡住，允许重做
HOST_TIMEOUT_SECONDS = {'normal': 120, 'enhanced': 120}
BUSY_RETRIES = 3
BUSY_WAIT_SECONDS = 2
WRONG_EVIDENCE = '页面识别，家长确认'
MAX_ITEMS = 60
DEFAULT_DIFFICULTY = 3
# 模型判对的题只留题干开头，最多这么多个字（设计 6.2）
RIGHT_STEM_CHARS = 40
# 整页整理和单题补全调模型的参数：随机度低一些，返回长度上限大一些（设计 6.2）
SCAN_MAX_TOKENS = 8000
SCAN_TEMPERATURE = 0.2
MODEL_FAILED_TEXT = '文本模型请求失败，请检查模型配置和余额'
MISSING_IMAGE_TEXT = '照片找不到了'
# run_page 最多走几步（正常最多 5 步），防止意外的死循环
MAX_STEPS = 8
INCOMPLETE_REASON = '模型返回的内容不完整，请对照原图'
NO_VERDICT_REASON = '模型没有给出明确判断，请对照原图'

# 模型输出里的文字字段、以及用户可编辑的文字字段
TEXT_FIELDS = ('question_no', 'parsed_question', 'wrong_answer', 'reason', 'answer', 'analysis')
EDIT_TEXT_FIELDS = ('question_no', 'parsed_question', 'wrong_answer', 'answer', 'analysis')
# 给用户看的字段中文名
FIELD_LABELS = {'question_no': '题号', 'parsed_question': '题干', 'wrong_answer': '学生的答案',
                'answer': '正确答案', 'analysis': '解析'}

_CHANGES_LIBRARY_PATH = re.compile(r'/api/scan/pages/\d+/items/\d+/(accept|withdraw)')


class ScanError(ValueError):
    """整页识别的业务错误，detail 是给用户看的中文说明。"""

    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


# ---------------------------------------------------------------- 健康检查

def interpret_health(status, body):
    """解读主机健康检查结果：200、ok 为真、契约版本匹配才算可用。"""
    if status != 200 or not isinstance(body, dict):
        return False
    return body.get('ok') is True and body.get('contract') == CONTRACT_VERSION


# ---------------------------------------------------------------- 提示词

def format_catalog(catalog):
    """把考点清单排成一行一个考点的文本，格式：编号 名称。"""
    lines = []
    for group in catalog or []:
        lines.append('【%s】' % group.get('name', ''))
        for point in group.get('points') or []:
            lines.append('  %s %s' % (point.get('id'), point.get('name', '')))
    return '\n'.join(lines) if lines else '（没有考点清单，考点留空）'


def _scope_line(subject_name, grade):
    """拼出学科和年级的说明句。"""
    grade_text = '%s 年级' % grade if grade else '年级不详'
    return '学科：%s，%s。' % (subject_name, grade_text)


def _knowledge_rules(catalog):
    """考点和难度的选择规则，整页提示词和单题补全提示词共用（错因已停用，不再让模型填）。"""
    return (
        '考点只能从下面的清单里选编号（knowledge_point_ids 是编号数组，primary_knowledge_point_id '
        '是其中最主要的一个；选了考点就必须给主考点）。清单里没有合适的就留空，不要编造编号：\n%s\n\n'
        '难度 difficulty 是 1 到 5 的整数。'
        % format_catalog(catalog)
    )


def _ocr_block(ocr_text, enhanced_text):
    """整页读图文字的提示词片段（有重扫文字时两份都给），整页整理和单题补全共用。"""
    parts = ['下面是整页读图得到的文字（OCR）：', '<<<OCR', ocr_text or '', 'OCR>>>']
    if enhanced_text:
        parts += [
            '',
            '下面是把同一页分段重新读取的结果。它和上面那份是同一张图，两份对照着用：'
            '一份读得不清的地方，参考另一份来补全，以更合理的为准。',
            '<<<OCR_ENHANCED',
            enhanced_text,
            'OCR_ENHANCED>>>',
        ]
    return parts


def build_page_prompt(subject_name, grade, semester, ocr_text, enhanced_text, catalog):
    """拼整页整理的提示词：要求模型逐题判断对错并返回 {"questions": [...]}。"""
    parts = [
        '你是一位中小学老师，要把一张作业或试卷照片读出来的文字整理成逐题的结构化结果。',
        _scope_line(subject_name, grade),
        '',
        *_ocr_block(ocr_text, enhanced_text),
        '',
        '请把这一页的每一道题都列出来，按卷面顺序，只返回 JSON：{"questions": [ ... ]}。'
        '一道大题下面有 (1)(2)… 小题、并且小题各有答案的，每个小题单独列一项。每道题的字段（按这个顺序写）：',
        '- question_no：题号，带上大题号和小题号，例如"二、4(3)"；卷面上没有大题号就只写题号。',
        '- parsed_question：完整题干（判为 right 的题例外，见下）。'
        '数学公式用 LaTeX：行内写 \\(...\\)，独立公式写 \\[...\\]。'
        'wrong_answer、solution、reason、answer、analysis 里的公式也一样，每个公式都要写在 \\(...\\) 里，'
        '不能直接写 \\frac{1}{2} 这样不带边界的公式。',
        '- wrong_answer：学生写的最终答案，读不出就留空字符串。',
        '- solution：你自己的演算，一两行，写出关键步骤和最终结果。每道题都要先写它，再下判断。',
        '- verdict：wrong（做错了）、right（做对了）或 unsure（拿不准）。',
        '- reason：一句话，固定写成"学生最终答案 …，正确答案 …"，例如"学生最终答案 x²+3，正确答案 x³−3"。',
        '- flags：读图异常标记数组，没有就写 []。只能用这四种：'
        'broken_formula（公式或算式不完整、括号不配对、数字明显不合理）、'
        'unsolvable（按读到的题干解不出，或条件不够）、'
        'merged（像是两道题或题干和演算混在了一起）、'
        'figure_needed（题目依赖图形或表格，但文字里没有相应条件）。',
        '- verdict 为 wrong 或 unsure 的题，还要给：answer（正确答案）、analysis（解析）、'
        'knowledge_point_ids、primary_knowledge_point_id、difficulty。',
        '- verdict 为 right 的题只给四个字段：question_no、parsed_question（只写题干开头，不超过 40 个字，'
        '不要完整题干）、solution、verdict。不要给学生的答案、判断理由、答案、解析、考点和难度，'
        '这样整页返回得快，也不会超出长度。',
        '',
        '判断对错的规则：先在 solution 里自己把题做一遍，再和学生的最终答案比对。',
        '1. 学生的最终答案读得出、和你算的不一样：先把你的演算再仔细复查一遍，确认是你算对了，才判 wrong。',
        '2. 学生的最终答案读得出、和你算的一样（或等价）：right。对错只看最终答案：'
        '过程写得乱、有涂改、有笔误、步骤不规范，只要最终答案对，一律 right，不许因为过程判 wrong。',
        '3. 学生的作答读不出，或者你自己解不出，或者是没有标准答案的题型（作图、作文、开放题）：unsure。',
        '4. 没有作答（空着）按做错处理：wrong，reason 写"没有作答"。',
        '5. 不许猜学生写了什么：看不清就是看不清，wrong_answer 留空并判 unsure。',
        '6. 只是书写形式不同不算错，例如 0.5 和 1/2、化简前后的同一个数，都按做对（0.5 和 1/2 不算错）。',
        '7. 例外：学生的答案里有字母（代数式）时，书写规范本身就是考点，要逐条检查：'
        '数字和字母相乘，数字写在字母前面（a·0.8、a×10 都要写成 0.8a、10a）；字母之间的乘号省略；'
        '带分数系数要化成假分数（1\\frac{2}{5}x 写成 \\frac{7}{5}x）；除法写成分数形式（(36-x)÷a 写成 \\frac{36-x}{a}）；'
        '和或差后面带单位时要加括号。值相等但违反任意一条的，判 wrong，reason 写明违反哪条。',
        '',
        _knowledge_rules(catalog),
        '',
        '文字里看得出不对劲时一定要打 flags 标记，不要硬猜。不要输出 JSON 以外的任何内容。',
        JSON_BACKSLASH_RULE,
    ]
    return '\n'.join(parts)


def build_fill_prompt(subject_name, grade, item, ocr_text, enhanced_text, catalog):
    """拼单题补全的提示词：给整页文字和这道题的题号、题干开头，只补全这一道（设计 8.4）。"""
    parts = [
        '你是一位中小学老师。下面是一张作业或试卷照片读出来的整页文字。'
        '家长认为其中有一道题学生做错了，请在整页文字里找到这道题，只补全这一道题的信息。',
        _scope_line(subject_name, grade),
        '',
        *_ocr_block(ocr_text, enhanced_text),
        '',
        '要补全的题：',
        '题号：%s' % (item.get('question_no') or '（没有题号）'),
        '题干开头：%s' % (item.get('parsed_question') or '（没有）'),
        '',
        '只返回这一道题的 JSON（一个对象），字段：',
        '- parsed_question：完整题干。',
        '- wrong_answer：学生写的答案，读不出就留空字符串，不许猜。',
        '- answer：正确答案。',
        '- analysis：解析。',
        '- knowledge_point_ids、primary_knowledge_point_id、difficulty。',
        '数学公式用 LaTeX：行内 \\(...\\)，独立 \\[...\\]。每个字段里的每个公式都要写在 \\(...\\) 里，'
        '不能直接写 \\frac{1}{2} 这样不带边界的公式。',
        '',
        _knowledge_rules(catalog),
        '不要输出 JSON 以外的任何内容。',
        JSON_BACKSLASH_RULE,
    ]
    return '\n'.join(parts)


# ---------------------------------------------------------------- 清洗

def _is_int(value):
    """是不是整数（排除 bool）。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _number_text(value):
    """数字（非 bool）转成文字，3 和 3.0 都得 "3"；不是数字返回 None。"""
    if _is_int(value):
        return str(value)
    if isinstance(value, float) and value == value and abs(value) != float('inf'):
        return str(int(value)) if value == int(value) else str(value)
    return None


def _model_id(value):
    """模型给的考点编号转成整数：认整数、值为整数的小数（101.0）和纯数字字符串（"101"），其他返回 None。

    模型常把编号写成字符串；只认整数的话，整页的考点会被全部丢掉。
    """
    if _is_int(value):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _clean_ids(raw_ids, catalog_ids):
    """考点编号：只留在清单里的编号（转成整数），去重保序。"""
    result = []
    for value in raw_ids if isinstance(raw_ids, list) else []:
        point_id = _model_id(value)
        if point_id is not None and point_id in catalog_ids and point_id not in result:
            result.append(point_id)
    return result


def _clean_knowledge(raw, catalog_ids):
    """清洗考点和主考点：主考点无效时，只剩一个考点就用它，否则为空。"""
    ids = _clean_ids(raw.get('knowledge_point_ids'), catalog_ids)
    primary = _model_id(raw.get('primary_knowledge_point_id'))
    if primary not in ids:
        primary = ids[0] if len(ids) == 1 else None
    return ids, primary


def _clean_difficulty(value):
    """难度必须是 1–5 的整数，否则取 3。"""
    if _is_int(value) and 1 <= value <= 5:
        return value
    return DEFAULT_DIFFICULTY


def blank_item(seq):
    """一道空白题（手工加一道用）。"""
    return {
        'seq': seq, 'question_no': '', 'parsed_question': '', 'wrong_answer': '',
        'verdict': 'wrong', 'reason': '', 'flags': [], 'answer': '', 'analysis': '',
        'knowledge_point_ids': [], 'primary_knowledge_point_id': None,
        'difficulty': DEFAULT_DIFFICULTY, 'state': 'open', 'question_id': None,
        'edited': False, 'source': 'manual',
    }


# ---------------------------------------------------------------- 没加边界的公式
#
# 模型常把答案、理由里的公式直接写成 \frac{61}{40}，不加 \( \)，页面上就显示成原始代码，
# 公式校验也查不到。清洗时把这种"裸公式"包上 \( \)；已经在 \( \)、\[ \]、$$ $$ 里的不动。
# （注释里的反斜杠只是说明，不是转义。）
_MATH_SPAN = re.compile(r'\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$', re.DOTALL)
# 一段裸公式：只含 ASCII 字母数字、运算符和括号（不含中文和中文标点），并且至少有一个 \命令
_BARE_MATH = re.compile(r'[A-Za-z0-9{}^_+\-*/=().|<>!×÷·\s]*\\[A-Za-z]+[A-Za-z0-9\\{}^_+\-*/=().|<>!×÷·\s]*')


def _wrap_run(match):
    """把一段裸公式包上 \\( \\)，两头的空白和句末标点留在外面。"""
    run = match.group(0)
    core = run.strip()
    while core and core[-1] in '.,':
        core = core[:-1]
    if '\\' not in core:
        return run
    start = run.index(core)
    return run[:start] + '\\(' + core + '\\)' + run[start + len(core):]


def wrap_bare_math(text):
    """把文字里没加边界的 LaTeX 公式包上 \\( \\)，已经加了边界的部分原样保留。"""
    if not isinstance(text, str) or '\\' not in text:
        return text
    pieces, position = [], 0
    for span in _MATH_SPAN.finditer(text):
        pieces.append(_BARE_MATH.sub(_wrap_run, text[position:span.start()]))
        pieces.append(span.group(0))
        position = span.end()
    pieces.append(_BARE_MATH.sub(_wrap_run, text[position:]))
    return ''.join(pieces)


def _clean_item(raw, seq, catalog_ids):
    """清洗模型返回的一道题，得到完整的草稿项。"""
    item = blank_item(seq)
    item['source'] = 'model'
    incomplete = False
    for field in TEXT_FIELDS:
        value = raw.get(field)
        if value is None:
            continue
        if isinstance(value, str):
            item[field] = value if field == 'question_no' else wrap_bare_math(value)
        elif field == 'question_no' and _number_text(value) is not None:
            item[field] = _number_text(value)  # 题号被写成数字时转成文字
        else:
            incomplete = True  # 文字字段不是字符串：置空并标"拿不准"
    verdict = raw.get('verdict')
    item['verdict'] = verdict if verdict in VERDICTS else 'unsure'
    flags = raw.get('flags')
    for flag in flags if isinstance(flags, list) else []:
        if isinstance(flag, str) and flag in FLAGS and flag not in item['flags']:
            item['flags'].append(flag)
    if incomplete:
        item['verdict'] = 'unsure'
        item['reason'] = INCOMPLETE_REASON
    elif item['verdict'] == 'unsure' and verdict not in VERDICTS and not item['reason']:
        item['reason'] = NO_VERDICT_REASON
    if item['verdict'] == 'right':
        # 做对的题不带答案、解析、考点，难度取默认值；
        # 题干只留开头（模型没照做、给了完整题干时这里截短），补成错题时再补全
        item['answer'] = item['analysis'] = ''
        item['parsed_question'] = item['parsed_question'][:RIGHT_STEM_CHARS]
        return item
    item['knowledge_point_ids'], item['primary_knowledge_point_id'] = _clean_knowledge(raw, catalog_ids)
    item['difficulty'] = _clean_difficulty(raw.get('difficulty'))
    return item


def clean_items(raw, catalog_ids):
    """清洗模型返回的整页结果：不信任模型，坏的字段丢掉或降级为"拿不准"。"""
    questions = raw.get('questions') if isinstance(raw, dict) else None
    if not isinstance(questions, list):
        return []
    items = []
    for entry in questions:
        if not isinstance(entry, dict):
            continue  # 不是对象的项丢掉，不占序号
        if len(items) >= MAX_ITEMS:
            break
        items.append(_clean_item(entry, len(items), catalog_ids))
    return items


def _text_or_empty(raw, field):
    """取一个文字字段：是字符串就原样返回，否则（缺失、类型不对）返回空串。"""
    value = raw.get(field)
    return wrap_bare_math(value) if isinstance(value, str) else ''


def clean_fill(raw, catalog_ids):
    """清洗单题补全的结果，返回七个字段（完整题干、学生的答案、答案、解析、考点、主考点、难度），规则同 clean_items。"""
    raw = raw if isinstance(raw, dict) else {}
    ids, primary = _clean_knowledge(raw, catalog_ids)
    return {
        'parsed_question': _text_or_empty(raw, 'parsed_question'),
        'wrong_answer': _text_or_empty(raw, 'wrong_answer'),
        'answer': _text_or_empty(raw, 'answer'),
        'analysis': _text_or_empty(raw, 'analysis'),
        'knowledge_point_ids': ids,
        'primary_knowledge_point_id': primary,
        'difficulty': _clean_difficulty(raw.get('difficulty')),
    }


def merge_fill(item, fill):
    """把补全结果合进这道题：模型没给（空的）题干、学生的答案沿用原来的，其余字段以补全结果为准。"""
    merged = dict(item, **fill)
    for field in ('parsed_question', 'wrong_answer'):
        if not fill.get(field, '').strip():
            merged[field] = item.get(field, '')
    return merged


# ---------------------------------------------------------------- 流程判断

def needs_rescan(items, rescan_used, rescan_enabled):
    """有任何一道题带读图异常标记，且没重扫过、允许重扫时，才需要重扫。"""
    if rescan_used or not rescan_enabled:
        return False
    return any(item.get('flags') for item in items)


def interpret_ocr(status, body):
    """解读主机读图的返回：ok / busy / failed，并给出用户文字和排查细节。"""
    result = {'kind': 'failed', 'text': '', 'elapsed_ms': None, 'user_text': '读图没成功', 'detail': ''}
    if not isinstance(body, dict):
        return result
    detail = body.get('detail')
    result['detail'] = detail if isinstance(detail, str) else ''
    claims_ok = status == 200 and body.get('ok') is True
    # 契约版本必须是 1：带了别的版本，或者声称成功却没带版本，都按版本不一致处理
    if ('contract' in body and body.get('contract') != CONTRACT_VERSION) or (
            claims_ok and 'contract' not in body):
        result['user_text'] = '识别服务版本不一致'
        return result
    if status == 503 and body.get('code') == 'busy':
        result['kind'] = 'busy'
        return result
    text = body.get('text')
    if status == 200 and body.get('ok') is True and isinstance(text, str) and text.strip():
        elapsed = body.get('elapsed_ms')
        result.update(kind='ok', text=text, user_text='',
                      elapsed_ms=elapsed if _is_int(elapsed) else None)
    return result


def next_step(page, now_seconds):
    """页面下一步该做什么：read / analyze / rescan / working（别人正在做）/ None（不用做）。"""
    status = page.get('status')
    if status in ('ready', 'closed'):
        return None
    started = page.get('step_started_at')
    if (status in ('reading', 'analyzing', 'rescanning') and started is not None
            and now_seconds - started <= STALE_SECONDS):
        return 'working'
    if not page.get('ocr_text'):
        return 'read'  # 没有读图文字，一律从读图开始
    if status == 'rescanning':
        return 'rescan'
    return 'analyze'


def failed_read(user_text, detail=''):
    """一个"读图失败"的结果，格式同 interpret_ocr（照片找不到等不经过主机的失败用）。"""
    return {'kind': 'failed', 'text': '', 'elapsed_ms': None, 'user_text': user_text, 'detail': detail}


async def read_with_retries(fetch, sleep):
    """调一次主机读图：fetch() 返回 (状态码, JSON)；主机忙时等一会儿重试，重试完仍忙按失败处理。

    返回 interpret_ocr 的结果。后端和回归脚本共用，sleep 由调用方传入（测试时可换成假的）。
    """
    for attempt in range(BUSY_RETRIES + 1):
        status, body = await fetch()
        result = interpret_ocr(status, body)
        if result['kind'] != 'busy':
            return result
        if attempt < BUSY_RETRIES:
            await sleep(BUSY_WAIT_SECONDS)
    return dict(result, kind='failed', detail=result['detail'] or 'busy')


# ---------------------------------------------------------------- 解析模型返回的 JSON
#
# 模型常把 LaTeX 的反斜杠原样写进 JSON 字符串：\( 、\frac、\begin。按 JSON 规则，\( 是非法转义
# （整页解析失败），\f、\b 又会被悄悄读成换页符、退格符（公式被读坏）。所以解析前先把这些反斜杠补成两个。

# 提示词里提醒模型的一句话
JSON_BACKSLASH_RULE = ('JSON 字符串里的每个反斜杠都要写成两个，'
                       '例如 \\\\(x^2\\\\)、\\\\frac{1}{2}、\\\\times。')
# 解析失败时记进 timings 的原文片段，出错位置前后各取这么多字
PARSE_HINT_CHARS = 80
_HEX_DIGITS = set('0123456789abcdefABCDEF')


class ModelJsonError(ValueError):
    """模型返回的内容解析不出 JSON；hint 是出错位置附近的原文，方便排查。"""

    def __init__(self, hint):
        """记录排查用的片段。"""
        super().__init__(hint)
        self.hint = hint


def repair_backslashes(text):
    """把 JSON 文本里属于 LaTeX 的单个反斜杠补成两个，正常的 JSON 转义原样保留。

    规则（逐个看反斜杠后面的字符）：
    - \\\\、\\"、\\/、\\uXXXX：合法转义，原样保留；
    - \\b \\f \\n \\r \\t 后面紧跟小写字母（\\frac、\\begin、\\neq、\\times）：是 LaTeX 命令，补成两个；
    - \\b \\f \\n \\r \\t 后面不是小写字母（换行后接中文、空格、标点、大写字母）：当作真的转义字符保留；
    - 其他（\\(、\\[、\\{、\\Delta、\\,）：JSON 里不合法，补成两个。
    """
    result = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char != '\\':
            result.append(char)
            index += 1
            continue
        if index + 1 >= length:
            result.append('\\\\')  # 末尾孤零零的反斜杠
            break
        following = text[index + 1]
        after = text[index + 2] if index + 2 < length else ''
        if following in '\\"/':
            result.append(char + following)
        elif following == 'u' and len(text[index + 2:index + 6]) == 4 and set(text[index + 2:index + 6]) <= _HEX_DIGITS:
            result.append(text[index:index + 6])
            index += 6
            continue
        elif following in 'bfnrt' and not ('a' <= after <= 'z'):
            result.append(char + following)
        else:
            result.append('\\\\' + following)
        index += 2
    return ''.join(result)


def parse_model_json(text):
    """把模型的回答解析成 JSON：去掉 ``` 围栏和前后说明文字，补好 LaTeX 反斜杠再解析。

    解析不出时抛 ModelJsonError，hint 里带出错位置、总长度和附近的原文。
    """
    content = (text or '').strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1] if '\n' in content else ''
        content = content.rsplit('```', 1)[0]
    # 只取第一个 { 或 [ 到最后一个 } 或 ] 之间的部分，去掉模型在前后加的说明
    starts = [position for position in (content.find('{'), content.find('[')) if position >= 0]
    end = max(content.rfind('}'), content.rfind(']'))
    if starts and end > min(starts):
        content = content[min(starts):end + 1]
    repaired = repair_backslashes(content)
    try:
        return json.loads(repaired)
    except ValueError as error:
        position = getattr(error, 'pos', 0) or 0
        snippet = repaired[max(0, position - PARSE_HINT_CHARS):position + PARSE_HINT_CHARS]
        raise ModelJsonError('%s；位置 %d / 共 %d 字；附近原文：%s' % (
            getattr(error, 'msg', str(error)), position, len(repaired), snippet))


def find_parse_hint(error):
    """在异常链（error 本身、__cause__、__context__）里找 ModelJsonError 的 hint，找不到返回 None。"""
    seen = 0
    while error is not None and seen < 5:
        if isinstance(error, ModelJsonError):
            return error.hint
        error = error.__cause__ or error.__context__
        seen += 1
    return None


def describe_model_error(error):
    """模型调用失败时给用户看的一句话，以及排查用的异常类型名。

    带 detail 文字的（接口层的 HTTPException、回归脚本的模型错误）用它的文字，类型名返回 None；
    其他运行时异常（网络超时等）统一给一句模型失败的提示，并返回异常类型名记进 timings。
    """
    detail = getattr(error, 'detail', None)
    if isinstance(detail, str) and detail:
        return detail, None
    return MODEL_FAILED_TEXT, type(error).__name__


def _elapsed_ms(started):
    """从 started（time.monotonic() 的值）到现在过了多少毫秒。"""
    return int((time.monotonic() - started) * 1000)


# ---------------------------------------------------------------- 识别的三个步骤（后端和回归脚本共用）
#
# 每个步骤：调外面传进来的读图 / 整理函数，把用时和排查信息写进 timings（原地修改），
# 返回这一步结束后要写回这一页的字段（至少有 status）。步骤本身不碰数据库。


def after_read(result):
    """读图之后：成功转 analyzing 并存下文字；失败转 failed，用户看提示文字。"""
    if result['kind'] == 'ok':
        return {'status': 'analyzing', 'ocr_text': result['text'], 'error': None}
    return {'status': 'failed', 'error': result['user_text']}


def after_analysis(items, rescan_used, rescan_enabled):
    """整理成功之后：存题目草稿；需要重扫转 rescanning，否则 ready。"""
    rescan = needs_rescan(items, rescan_used, rescan_enabled)
    return {'status': 'rescanning' if rescan else 'ready', 'error': None, 'items': items}


def after_analysis_failure(error_text, enhanced_text, previous_items):
    """整理失败之后：重扫后的第二次整理失败、且已有第一次的结果时，保留它直接 ready；否则转 failed。"""
    if enhanced_text and previous_items:
        return {'status': 'ready', 'error': None}
    return {'status': 'failed', 'error': error_text}


def after_rescan(result):
    """重扫之后：成功转 analyzing 并存下重扫文字；失败直接 ready，保留第一次的题目草稿。"""
    if result['kind'] == 'ok':
        return {'status': 'analyzing', 'ocr_text_enhanced': result['text']}
    return {'status': 'ready'}


async def step_read(read_text, timings):
    """读图一步：read_text('normal') 返回 interpret_ocr 格式的结果。"""
    clock = time.monotonic()
    result = await read_text('normal')
    timings['read_ms'] = _elapsed_ms(clock)
    if result['kind'] == 'ok':
        if result['elapsed_ms'] is not None:
            timings['host_read_ms'] = result['elapsed_ms']
    else:
        timings['host_detail'] = result['detail']  # 主机细节只记进 timings，不给用户看
    return after_read(result)


async def step_analyze(analyze, ocr_text, enhanced_text, previous_items, rescan_used, rescan_enabled, timings):
    """整理一步：analyze(读图文字, 重扫文字) 返回清洗后的题目；模型失败时抛异常。"""
    clock = time.monotonic()
    # 重扫后的第二次整理单独记用时
    timing_key = 'analyze2_ms' if enhanced_text else 'analyze_ms'
    try:
        items = await analyze(ocr_text, enhanced_text)
    except Exception as error:
        error_text, error_type = describe_model_error(error)
        if error_type:
            timings['model_error_type'] = error_type
        parse_hint = find_parse_hint(error)
        if parse_hint:
            timings['model_parse_hint'] = parse_hint  # 模型返回的内容解析不出时，记下出错位置附近的原文
        fields = after_analysis_failure(error_text, enhanced_text, previous_items)
        if fields['status'] == 'ready':
            timings['analyze2_error'] = error_text  # 保留第一次结果时，失败原因只记进 timings
    else:
        fields = after_analysis(items, rescan_used, rescan_enabled)
    timings[timing_key] = _elapsed_ms(clock)
    return fields


async def step_rescan(read_text, timings):
    """强化重扫一步：read_text('enhanced') 返回 interpret_ocr 格式的结果。"""
    clock = time.monotonic()
    result = await read_text('enhanced')
    timings['rescan_ms'] = _elapsed_ms(clock)
    if result['kind'] == 'ok':
        if result['elapsed_ms'] is not None:
            timings['host_rescan_ms'] = result['elapsed_ms']
    else:
        timings['host_detail'] = result['detail']
    return after_rescan(result)


async def run_page(read_text, analyze, rescan_enabled):
    """把一页从头走到底（回归脚本用）：读图 → 整理 → 需要时重扫一次 → 再整理。

    read_text(mode) 返回 interpret_ocr 格式的结果；analyze(读图文字, 重扫文字) 返回清洗后的题目，
    模型失败时抛异常。每一步做什么由 next_step 决定，和后端逐请求推进时完全一样。
    返回 {'status','items','ocr_text','ocr_text_enhanced','rescan_used','timings','error'}。
    """
    page = {'status': 'uploaded', 'step_started_at': None, 'items': [], 'ocr_text': None,
            'ocr_text_enhanced': None, 'rescan_used': 0, 'timings': {}, 'error': None}
    for _ in range(MAX_STEPS):
        if page['status'] in ('ready', 'failed'):
            break
        step = next_step(page, 0)
        if step == 'read':
            fields = await step_read(read_text, page['timings'])
        elif step == 'analyze':
            fields = await step_analyze(analyze, page['ocr_text'], page['ocr_text_enhanced'], page['items'],
                                        page['rescan_used'], rescan_enabled, page['timings'])
        else:
            page['rescan_used'] = 1  # 和后端认领重扫时一样：开始重扫就记下，之后不再重扫
            fields = await step_rescan(read_text, page['timings'])
        page.update(fields)
    return {key: page[key] for key in ('status', 'items', 'ocr_text', 'ocr_text_enhanced', 'rescan_used',
                                       'timings', 'error')}


# ---------------------------------------------------------------- 编辑与入库

def clean_edit(payload):
    """校验用户的修改：只认可编辑的字段，返回其中提供且合法的部分。"""
    if not isinstance(payload, dict):
        raise ScanError('修改内容格式不对')
    edit = {}
    for field in EDIT_TEXT_FIELDS:
        if field in payload:
            if not isinstance(payload[field], str):
                raise ScanError('%s必须是文字' % FIELD_LABELS[field])
            edit[field] = payload[field]
    if 'knowledge_point_ids' in payload:
        ids = payload['knowledge_point_ids']
        if not isinstance(ids, list) or not all(_is_int(value) for value in ids):
            raise ScanError('考点格式不对')
        edit['knowledge_point_ids'] = list(dict.fromkeys(ids))
    if 'primary_knowledge_point_id' in payload:
        primary = payload['primary_knowledge_point_id']
        if primary is not None and not _is_int(primary):
            raise ScanError('主考点格式不对')
        edit['primary_knowledge_point_id'] = primary
    if 'knowledge_point_ids' in edit and 'primary_knowledge_point_id' in edit:
        # 两个字段同时给时，在这里就能核对一致性
        primary = edit['primary_knowledge_point_id']
        if primary is not None and primary not in edit['knowledge_point_ids']:
            raise ScanError('主考点必须是所选考点之一')
        if edit['knowledge_point_ids'] and primary is None:
            raise ScanError('选了考点就要选一个主考点')
    # 错因已停用：旧页面如果还传 error_types，直接忽略
    if 'difficulty' in payload:
        if not _is_int(payload['difficulty']) or not 1 <= payload['difficulty'] <= 5:
            raise ScanError('难度必须是 1 到 5')
        edit['difficulty'] = payload['difficulty']
    return edit


def question_payload(page, item):
    """把一页和其中一道题拼成交给错题保存逻辑的字段。"""
    return {
        'subject_id': page['subject_id'], 'grade': page['grade'], 'semester': page['semester'],
        'question_no': item['question_no'], 'parsed_question': item['parsed_question'],
        'answer': item['answer'], 'analysis': item['analysis'], 'wrong_answer': item['wrong_answer'],
        'difficulty': item['difficulty'],
        'knowledge_point_ids': item['knowledge_point_ids'],
        'primary_knowledge_point_id': item['primary_knowledge_point_id'],
        'original_image': page['image'], 'original_images': [page['image']],
        'wrong_evidence': WRONG_EVIDENCE,
    }


def changes_library(method, path):
    """这个请求会不会改动错题库（只有录入一道、撤回会；"全部录入"是页面逐道调录入一道）。"""
    return method == 'POST' and _CHANGES_LIBRARY_PATH.fullmatch(path) is not None
