"""录题规则：卷子和题目的校验、默认值，以及"直接入库还是待核对"的判断。

本模块只含纯函数，只用标准库，不访问数据库和网络，也不读取时钟
（"今天"由调用方传入）。
"""

import datetime
import math
import re

SPEC_VERSION = 1
PAPER_TYPES = ('homework', 'chapter_practice', 'exam')
EXAM_KINDS = ('unit', 'midterm', 'final', 'other')
REVIEW_REASONS = ('wrong_unclear', 'text_unclear', 'kp_unsure', 'other')
MAX_QUESTIONS = 100

# 上传接口返回的图片路径：年/月/8位十六进制_文件名
# 数字只认半角 0-9（\d 会放过全角数字），文件名部分不许有斜杠、反斜杠和控制字符；匹配一律用 fullmatch
IMAGE_KEY_PATTERN = re.compile(r'[0-9]{4}/[0-9]{2}/[0-9a-f]{8}_[^/\\\x00-\x1f\x7f]+')
DATE_PATTERN = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')

# 题目里按文字处理的字段，缺省为空字符串，对应的中文名用于报错
QUESTION_TEXT_FIELDS = (
    ('question_no', '题号'),
    ('parsed_question', '题干'),
    ('answer', '正确答案'),
    ('analysis', '解析'),
    ('wrong_answer', '孩子的答案'),
    ('wrong_evidence', '判错依据'),
    ('review_note', '疑问说明'),
)

BROKEN_BACKSLASH_TEXT = ('公式里的反斜杠没有写对：JSON 里每个反斜杠要写成两个，比如 \\\\frac、\\\\times。'
                         '请改好后重新提交。')
# 公式的三种写法：\( \)、\[ \]、$$ $$；用最短匹配，每个公式单独取出
MATH_SPAN_PATTERN = re.compile(r'\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$', re.DOTALL)

LOST_ROW_BREAK_TEXT = ('矩阵或多行公式里的换行没有写对：换行要写成两个反斜杠 \\\\（手写 JSON 时是四个）。'
                       '请改好后重新提交。')
# 公式里有换行的说明：多半是 \neq、\nu 的反斜杠没写对，也可能是真的想换行
MATH_NEWLINE_TEXT = ('公式里有换行：一个公式要写在同一行里，多行公式的行与行之间用两个反斜杠分开、不要另起一行。'
                     '如果本来就没想换行，那是 \\neq、\\nu 这类命令的反斜杠没有写对，'
                     'JSON 里每个反斜杠要写成两个。请改好后重新提交。')
# 矩阵和多行公式环境：环境里的换行必须是两个反斜杠
MATRIX_ENVIRONMENTS = ('matrix', 'pmatrix', 'bmatrix', 'Bmatrix', 'vmatrix', 'Vmatrix', 'smallmatrix', 'array',
                       'cases', 'aligned', 'align', 'align*', 'gathered', 'split')
MATRIX_PATTERN = re.compile(r'\\begin\{(' + '|'.join(re.escape(name) for name in MATRIX_ENVIRONMENTS)
                            + r')\}(.*?)\\end\{\1\}', re.DOTALL)
# 单个反斜杠（前后都不是反斜杠），后面是空白、环境结尾、数字、正负号，或恰好一个字母：丢了一个反斜杠的换行。
# 后面是两个以上字母的是正常命令（\frac、\cdot），是 , ; { } 等符号的是正常转义，都不算
LOST_ROW_BREAK_PATTERN = re.compile(r'(?<!\\)\\(?!\\)(?=\s|$|[0-9+\-]|[A-Za-z](?![A-Za-z]))')
OUTSIDE_BACKSLASH_TEXT = ('公式要写在 \\( \\) 或 \\[ \\] 里面，公式外面不能出现反斜杠'
                          '（文字换行就直接换行，不要写成 \\n 两个字符）。请改好后重新提交。')


class IntakeError(ValueError):
    """校验失败；detail 是给人看的中文说明。"""

    def __init__(self, detail):
        """记录中文说明。"""
        super().__init__(detail)
        self.detail = detail


def is_plain_int(value):
    """判断是不是整数；bool 是 int 的子类，必须排除。"""
    return isinstance(value, int) and not isinstance(value, bool)


def is_finite_number(value):
    """判断是不是有限的整数或小数；排除 bool、字符串、NaN 和无穷大。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def default_paper_name(subject_name, paper_date):
    """没写卷子名称时的默认名称：学科名 + 习题 + 日期。"""
    return '%s习题 %s' % (subject_name, paper_date)


def find_broken_backslash(text):
    """文字里有被写坏的反斜杠时返回一句给人看的说明，没有问题返回 None。

    JSON 里反斜杠没写成两个时，\\f、\\t、\\r、\\n、\\b 会变成换页、制表、回车、换行、退格。
    """
    # 换行以外的控制字符（含删除符 127）在正常文字里不会出现
    for char in text:
        code = ord(char)
        if (code < 32 and char != '\n') or code == 127:
            return BROKEN_BACKSLASH_TEXT
    # 公式内部不该有换行，\neq、\nu 被写坏时就是这样；公式外的换行是正常的
    for span in MATH_SPAN_PATTERN.finditer(text):
        if '\n' in span.group():
            return MATH_NEWLINE_TEXT
    # 矩阵、多行公式里丢了一个反斜杠的换行（两个反斜杠只写成了一个）
    for environment in MATRIX_PATTERN.finditer(text):
        if LOST_ROW_BREAK_PATTERN.search(environment.group(2)):
            return LOST_ROW_BREAK_TEXT
    # 去掉所有公式后还剩反斜杠：公式没写边界，或把换行写成了 \n 两个字符
    if '\\' in MATH_SPAN_PATTERN.sub('', text):
        return OUTSIDE_BACKSLASH_TEXT
    return None


def read_text(raw, key, label):
    """读取文字字段：没有或为空返回空字符串，不是文字就报错，坏反斜杠报错，去掉首尾空白。"""
    value = raw.get(key)
    if value is None:
        return ''
    if not isinstance(value, str):
        raise IntakeError('%s必须是文字' % label)
    # Windows 换行 \r\n 是正常的，先统一成 \n；单独的 \r（写坏的 \r 开头命令）仍会被下面查出来
    value = value.replace('\r\n', '\n')
    # 必须在去空白之前检查：换页、制表等本身算空白，去掉后就查不出来了
    problem = find_broken_backslash(value)
    if problem:
        raise IntakeError('%s：%s' % (label, problem))
    return value.strip()


def normalize_paper_date(raw_date, today):
    """检查卷子日期：不写取今天，格式必须是 YYYY-MM-DD，不能晚于今天。"""
    if raw_date is None or raw_date == '':
        return today
    if not isinstance(raw_date, str) or not DATE_PATTERN.fullmatch(raw_date):
        raise IntakeError('卷子日期格式不对，应写成 2026-11-10 这样')
    try:
        datetime.date.fromisoformat(raw_date)
    except ValueError:
        raise IntakeError('卷子日期不存在，请检查月份和日号')
    # 同为 YYYY-MM-DD，可以直接按字符串比较先后
    if raw_date > today:
        raise IntakeError('卷子日期不能是未来的日期')
    return raw_date


def normalize_paper_scores(raw):
    """检查得分和满分：要么都填要么都不填，都是不小于 0 的整数，得分不超过满分。"""
    score = raw.get('score')
    full_score = raw.get('full_score')
    if score is None and full_score is None:
        return None, None
    if score is None or full_score is None:
        raise IntakeError('得分和满分要么都填，要么都不填')
    if not is_finite_number(score) or not is_finite_number(full_score):
        raise IntakeError('得分和满分必须是有限的数字')
    if score < 0 or full_score < 0:
        raise IntakeError('得分和满分都不能小于 0')
    if score > full_score:
        raise IntakeError('得分不能大于满分')
    return score, full_score


def normalize_paper_images(raw_images):
    """检查照片路径列表：可以为空，每一项必须是上传接口返回的路径格式。"""
    if raw_images is None:
        return []
    if not isinstance(raw_images, list):
        raise IntakeError('照片必须是路径列表')
    for image in raw_images:
        if not isinstance(image, str) or not IMAGE_KEY_PATTERN.fullmatch(image):
            raise IntakeError('照片路径格式不对，请使用上传照片后返回的路径')
    return list(raw_images)


def normalize_range_number(raw, key, label, low, high):
    """读取有范围的整数（年级、学期）：不写返回 None，写了必须在范围内。"""
    value = raw.get(key)
    if value is None:
        return None
    if not is_plain_int(value) or not low <= value <= high:
        raise IntakeError('%s必须是 %d 到 %d 的整数' % (label, low, high))
    return value


def normalize_paper(raw, subject_name, today):
    """检查并补全一份卷子的信息，返回整理后的字典；不合格时抛 IntakeError。"""
    paper_type = raw.get('paper_type')
    if paper_type is None or paper_type == '':
        paper_type = 'homework'
    if paper_type not in PAPER_TYPES:
        raise IntakeError('卷子类型不对，只能是 %s' % '、'.join(PAPER_TYPES))

    # 考试细分只对考试有效：考试不写默认 other，其他类型一律忽略
    exam_kind = None
    if paper_type == 'exam':
        exam_kind = raw.get('exam_kind')
        if exam_kind is None or exam_kind == '':
            exam_kind = 'other'
        if exam_kind not in EXAM_KINDS:
            raise IntakeError('考试类型不对，只能是 %s' % '、'.join(EXAM_KINDS))

    paper_date = normalize_paper_date(raw.get('paper_date'), today)
    name = read_text(raw, 'name', '名称')
    if not name:
        name = default_paper_name(subject_name, paper_date)
    score, full_score = normalize_paper_scores(raw)
    return {
        'name': name,
        'paper_type': paper_type,
        'exam_kind': exam_kind,
        'paper_date': paper_date,
        'grade': normalize_range_number(raw, 'grade', '年级', 1, 12),
        'semester': normalize_range_number(raw, 'semester', '学期', 1, 2),
        'score': score,
        'full_score': full_score,
        'images': normalize_paper_images(raw.get('images')),
        'notes': read_text(raw, 'notes', '备注'),
    }


def normalize_question_page(raw_page, image_count):
    """检查题目来自第几张照片：有照片时必填且在范围内，没有照片时必须为空。"""
    if image_count == 0:
        if raw_page is not None:
            raise IntakeError('这份卷子没有照片，这道题不能填来自第几张照片')
        return None
    if not is_plain_int(raw_page) or not 1 <= raw_page <= image_count:
        raise IntakeError('这道题来自第几张照片没有写，或者超出了照片张数（共 %d 张）' % image_count)
    return raw_page


def normalize_error_type(raw_error_type, error_type_names):
    """整理错因：逗号分隔，去掉空格和重复项；有错因清单时逐项核对。"""
    if raw_error_type is None:
        return ''
    if not isinstance(raw_error_type, str):
        raise IntakeError('错因必须是文字')
    names = []
    # 同时接受中文逗号，避免手误
    for part in raw_error_type.replace('，', ',').split(','):
        part = part.strip()
        if part and part not in names:
            names.append(part)
    if error_type_names:
        for part in names:
            if part not in error_type_names:
                raise IntakeError('错因「%s」不在这个学科的错因清单里' % part)
    return ','.join(names)


def normalize_knowledge_points(raw):
    """检查考点编号：只看类型（整数列表、整数主考点），是否在目录里由调用方查。"""
    point_ids = raw.get('knowledge_point_ids')
    if point_ids is None:
        point_ids = []
    if not isinstance(point_ids, list) or not all(is_plain_int(item) for item in point_ids):
        raise IntakeError('考点必须用编号表示，不能用文字名称')
    unique_ids = []
    for item in point_ids:
        if item not in unique_ids:
            unique_ids.append(item)
    primary_id = raw.get('primary_knowledge_point_id')
    if primary_id is not None and not is_plain_int(primary_id):
        raise IntakeError('主考点必须用编号表示，不能用文字名称')
    return unique_ids, primary_id


def normalize_review_fields(raw):
    """检查待核对标记和原因：标为待核对时必须给出至少一个合法原因。"""
    needs_review = raw.get('needs_review')
    if needs_review is None:
        needs_review = False
    if not isinstance(needs_review, bool):
        raise IntakeError('是否待核对只能填 true 或 false')
    reasons = raw.get('review_reasons')
    if reasons is None:
        reasons = []
    if not isinstance(reasons, list):
        raise IntakeError('待核对原因必须是列表')
    for reason in reasons:
        if reason not in REVIEW_REASONS:
            raise IntakeError('待核对原因「%s」不认识，只能是 %s' % (reason, '、'.join(REVIEW_REASONS)))
    if needs_review and not reasons:
        raise IntakeError('标为待核对时，必须写明待核对的原因')
    return needs_review, list(reasons)


def normalize_question(raw, image_count, error_type_names):
    """检查并补全一道题，返回整理后的字典；不合格时抛 IntakeError。"""
    texts = {key: read_text(raw, key, label) for key, label in QUESTION_TEXT_FIELDS}
    if not texts['parsed_question']:
        raise IntakeError('题干必须填写')

    difficulty = raw.get('difficulty')
    if difficulty is None:
        difficulty = 3
    if not is_plain_int(difficulty) or not 1 <= difficulty <= 5:
        raise IntakeError('难度必须是 1 到 5 的整数')

    knowledge_point_ids, primary_id = normalize_knowledge_points(raw)
    needs_review, review_reasons = normalize_review_fields(raw)
    return {
        'page': normalize_question_page(raw.get('page'), image_count),
        'question_no': texts['question_no'],
        'parsed_question': texts['parsed_question'],
        'answer': texts['answer'],
        'analysis': texts['analysis'],
        'wrong_answer': texts['wrong_answer'],
        'wrong_evidence': texts['wrong_evidence'],
        'difficulty': difficulty,
        'error_type': normalize_error_type(raw.get('error_type'), error_type_names),
        'knowledge_point_ids': knowledge_point_ids,
        'primary_knowledge_point_id': primary_id,
        'needs_review': needs_review,
        'review_reasons': review_reasons,
        'review_note': texts['review_note'],
    }


def decide_review(question, catalog_available):
    """判断一道题直接入库还是待核对，返回 (状态, 原因列表)。

    原因去重，并按 REVIEW_REASONS 里的顺序排列。孩子的答案留空不影响；
    没有主考点也不算待核对：目录里找不到合适考点的题直接入库，记为未分类
    （用户 2026-11-11 决定）。catalog_available 保留在参数里，调用方不用改。
    """
    reasons = set()
    flagged = bool(question.get('needs_review'))
    if flagged:
        reasons.update(question.get('review_reasons') or [])
    if not (question.get('wrong_evidence') or '').strip():
        reasons.add('wrong_unclear')
        flagged = True
    if not flagged:
        return 'approved', []
    return 'pending', [reason for reason in REVIEW_REASONS if reason in reasons]
