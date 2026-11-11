"""整页识别录入的纯逻辑（不碰数据库和网络）。"""

import re

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
STALE_SECONDS = 150          # 一步超过这么久没结束，视为卡住，允许重做
HOST_TIMEOUT_SECONDS = {'normal': 70, 'enhanced': 130}
BUSY_RETRIES = 3
BUSY_WAIT_SECONDS = 2
WRONG_EVIDENCE = '页面识别，家长确认'
MAX_ITEMS = 60
# "全部录入"一次请求最多录几道。免费计划一次请求最多 50 次 D1 查询：
# 实测录一道约 10 次查询加 1 次公式校验，再加读页两次，3 道约 35 次，留出余量
ACCEPT_ALL_BATCH = 3
DEFAULT_DIFFICULTY = 3
INCOMPLETE_REASON = '模型返回的内容不完整，请对照原图'
NO_VERDICT_REASON = '模型没有给出明确判断，请对照原图'

# 模型输出里的文字字段、以及用户可编辑的文字字段
TEXT_FIELDS = ('question_no', 'parsed_question', 'wrong_answer', 'reason', 'answer', 'analysis')
EDIT_TEXT_FIELDS = ('question_no', 'parsed_question', 'wrong_answer', 'answer', 'analysis')
# 给用户看的字段中文名
FIELD_LABELS = {'question_no': '题号', 'parsed_question': '题干', 'wrong_answer': '孩子的答案',
                'answer': '正确答案', 'analysis': '解析'}

_CHANGES_LIBRARY_PATH = re.compile(r'/api/scan/pages/\d+/(items/\d+/(accept|withdraw)|accept-all)')


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


def _knowledge_rules(catalog, error_type_names):
    """考点与错因的选择规则，整页提示词和单题补全提示词共用。"""
    return (
        '考点只能从下面的清单里选编号（knowledge_point_ids 是编号数组，primary_knowledge_point_id '
        '是其中最主要的一个；选了考点就必须给主考点）。清单里没有合适的就留空，不要编造编号：\n%s\n\n'
        '错因（error_types）只能从这些名称里选：%s。没有合适的就留空数组。\n'
        '难度 difficulty 是 1 到 5 的整数。'
        % (format_catalog(catalog), '、'.join(error_type_names) if error_type_names else '（无）')
    )


def build_page_prompt(subject_name, grade, semester, ocr_text, enhanced_text, catalog, error_type_names):
    """拼整页整理的提示词：要求模型逐题判断对错并返回 {"questions": [...]}。"""
    parts = [
        '你是一位中小学老师，要把一张作业或试卷照片读出来的文字整理成逐题的结构化结果。',
        _scope_line(subject_name, grade),
        '',
        '下面是整页读图得到的文字（OCR）：',
        '<<<OCR',
        ocr_text or '',
        'OCR>>>',
    ]
    if enhanced_text:
        parts += [
            '',
            '下面是把同一页分段重新读取的结果。它和上面那份是同一张图，两份对照着用：'
            '一份读得不清的地方，参考另一份来补全，以更合理的为准。',
            '<<<OCR_ENHANCED',
            enhanced_text,
            'OCR_ENHANCED>>>',
        ]
    parts += [
        '',
        '请把这一页的每一道题都列出来，按卷面顺序，只返回 JSON：{"questions": [ ... ]}。每道题的字段：',
        '- question_no：卷面上印的题号，照原样。',
        '- parsed_question：完整题干。数学公式用 LaTeX：行内写 \\(...\\)，独立公式写 \\[...\\]。',
        '- wrong_answer：孩子写的答案，读不出就留空字符串。',
        '- verdict：wrong（做错了）、right（做对了）或 unsure（拿不准）。',
        '- reason：一句话判断理由，例如"孩子写 x²+3，应为 x³−3"。',
        '- flags：读图异常标记数组，没有就写 []。只能用这四种：'
        'broken_formula（公式或算式不完整、括号不配对、数字明显不合理）、'
        'unsolvable（按读到的题干解不出，或条件不够）、'
        'merged（像是两道题或题干和演算混在了一起）、'
        'figure_needed（题目依赖图形或表格，但文字里没有相应条件）。',
        '- verdict 为 wrong 或 unsure 的题，还要给：answer（正确答案）、analysis（解析）、'
        'knowledge_point_ids、primary_knowledge_point_id、error_types、difficulty。',
        '- verdict 为 right 的题只给 question_no、parsed_question（完整题干）、'
        'wrong_answer、verdict、reason，不用给答案、解析、考点、错因和难度。',
        '',
        '判断对错的规则：先自己把每道题做一遍，再和孩子的作答比对。',
        '1. 孩子的作答读得出、和你算的不一样：wrong。',
        '2. 孩子的作答读得出、和你算的一样：right。',
        '3. 孩子的作答读不出，或者你自己解不出，或者是没有标准答案的题型（作图、作文、开放题）：unsure。',
        '4. 没有作答（空着）按做错处理：wrong，reason 写"没有作答"。',
        '5. 不许猜孩子写了什么：看不清就是看不清，wrong_answer 留空并判 unsure。',
        '6. 只是书写形式不同不算错，例如 0.5 和 1/2、化简前后的同一个数，都按做对（0.5 和 1/2 不算错）。',
        '',
        _knowledge_rules(catalog, error_type_names),
        '',
        '文字里看得出不对劲时一定要打 flags 标记，不要硬猜。不要输出 JSON 以外的任何内容。',
    ]
    return '\n'.join(parts)


def build_fill_prompt(subject_name, grade, item, catalog, error_type_names):
    """拼单题补全的提示词：只针对这一道，返回答案、解析、考点、错因、难度。"""
    parts = [
        '你是一位中小学老师。下面这道题是从试卷照片里读出来的，请只针对这一道题补全信息。',
        _scope_line(subject_name, grade),
        '',
        '题号：%s' % (item.get('question_no') or ''),
        '题干：%s' % (item.get('parsed_question') or ''),
        '孩子的答案：%s' % (item.get('wrong_answer') or '（读不出）'),
        '',
        '只返回 JSON，字段：answer（正确答案）、analysis（解析）、knowledge_point_ids、'
        'primary_knowledge_point_id、error_types、difficulty。数学公式用 LaTeX：行内 \\(...\\)，独立 \\[...\\]。',
        '',
        _knowledge_rules(catalog, error_type_names),
        '不要输出 JSON 以外的任何内容。',
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


def _clean_ids(raw_ids, catalog_ids):
    """考点编号：只留在清单里的整数，去重保序。"""
    result = []
    for value in raw_ids if isinstance(raw_ids, list) else []:
        if _is_int(value) and value in catalog_ids and value not in result:
            result.append(value)
    return result


def _clean_knowledge(raw, catalog_ids):
    """清洗考点和主考点：主考点无效时，只剩一个考点就用它，否则为空。"""
    ids = _clean_ids(raw.get('knowledge_point_ids'), catalog_ids)
    primary = raw.get('primary_knowledge_point_id')
    if not (_is_int(primary) and primary in ids):
        primary = ids[0] if len(ids) == 1 else None
    return ids, primary


def _clean_error_types(raw_types, error_type_names):
    """错因名：只留清单里的，去重保序。"""
    result = []
    for value in raw_types if isinstance(raw_types, list) else []:
        if isinstance(value, str) and value in error_type_names and value not in result:
            result.append(value)
    return result


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
        'knowledge_point_ids': [], 'primary_knowledge_point_id': None, 'error_types': [],
        'difficulty': DEFAULT_DIFFICULTY, 'state': 'open', 'question_id': None,
        'edited': False, 'source': 'manual',
    }


def _clean_item(raw, seq, catalog_ids, error_type_names):
    """清洗模型返回的一道题，得到完整的草稿项。"""
    item = blank_item(seq)
    item['source'] = 'model'
    incomplete = False
    for field in TEXT_FIELDS:
        value = raw.get(field)
        if value is None:
            continue
        if isinstance(value, str):
            item[field] = value
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
        # 做对的题不带答案、解析、考点、错因，难度取默认值
        item['answer'] = item['analysis'] = ''
        return item
    item['knowledge_point_ids'], item['primary_knowledge_point_id'] = _clean_knowledge(raw, catalog_ids)
    item['error_types'] = _clean_error_types(raw.get('error_types'), error_type_names)
    item['difficulty'] = _clean_difficulty(raw.get('difficulty'))
    return item


def clean_items(raw, catalog_ids, error_type_names):
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
        items.append(_clean_item(entry, len(items), catalog_ids, error_type_names))
    return items


def clean_fill(raw, catalog_ids, error_type_names):
    """清洗单题补全的结果，只返回六个字段，规则同 clean_items。"""
    raw = raw if isinstance(raw, dict) else {}
    ids, primary = _clean_knowledge(raw, catalog_ids)
    return {
        'answer': raw['answer'] if isinstance(raw.get('answer'), str) else '',
        'analysis': raw['analysis'] if isinstance(raw.get('analysis'), str) else '',
        'knowledge_point_ids': ids,
        'primary_knowledge_point_id': primary,
        'error_types': _clean_error_types(raw.get('error_types'), error_type_names),
        'difficulty': _clean_difficulty(raw.get('difficulty')),
    }


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


def has_warning(item):
    """带读图异常标记且没被人改过，就算有提示。"""
    return bool(item.get('flags')) and not item.get('edited')


def accept_all_seqs(items):
    """"全部录入"包含的题：未处理、判断为做错、没有提示的。"""
    return [item['seq'] for item in items
            if item.get('state') == 'open' and item.get('verdict') == 'wrong' and not has_warning(item)]


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
    if 'error_types' in payload:
        types = payload['error_types']
        if not isinstance(types, list) or not all(isinstance(value, str) for value in types):
            raise ScanError('错因格式不对')
        edit['error_types'] = list(dict.fromkeys(types))
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
        'difficulty': item['difficulty'], 'error_type': ','.join(item['error_types']),
        'knowledge_point_ids': item['knowledge_point_ids'],
        'primary_knowledge_point_id': item['primary_knowledge_point_id'],
        'original_image': page['image'], 'original_images': [page['image']],
        'wrong_evidence': WRONG_EVIDENCE,
    }


def changes_library(method, path):
    """这个请求会不会改动错题库（只有录入、撤回、全部录入会）。"""
    return method == 'POST' and _CHANGES_LIBRARY_PATH.fullmatch(path) is not None
