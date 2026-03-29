"""
HTML工具函数
"""
import html
import re


def decode_html(text: str) -> str:
    """
    解码HTML实体，将如 &times; &divide; 等转换为实际字符

    Args:
        text: 包含HTML实体的文本

    Returns:
        解码后的文本
    """
    if not text:
        return text

    # 使用html库解码标准HTML实体
    text = html.unescape(text)

    # 处理一些常见的数学符号实体（确保兼容性）
    math_entities = {
        '&times;': '×',
        '&divide;': '÷',
        '&plusmn;': '±',
        '&minus;': '−',
        '&lt;': '<',
        '&gt;': '>',
        '&le;': '≤',
        '&ge;': '≥',
        '&ne;': '≠',
        '&approx;': '≈',
        '&frac12;': '½',
        '&frac13;': '⅓',
        '&frac14;': '¼',
        '&deg;': '°',
        '&cent;': '¢',
        '&pound;': '£',
        '&yen;': '¥',
        '&euro;': '€',
        '&sect;': '§',
        '&para;': '¶',
        '&bull;': '•',
        '&middot;': '·',
        '&hellip;': '…',
        '&prime;': '′',
        '&Prime;': '″',
        '&infin;': '∞',
        '&radic;': '√',
        '&sum;': '∑',
        '&prod;': '∏',
        '&part;': '∂',
        '&nabla;': '∇',
        '&exist;': '∃',
        '&forall;': '∀',
        '&isin;': '∈',
        '&notin;': '∉',
        '&subset;': '⊂',
        '&supset;': '⊃',
        '&cup;': '∪',
        '&cap;': '∩',
        '&int;': '∫',
        '&therefore;': '∴',
        '&because;': '∵',
        '&perp;': '⊥',
        '&平行;': '∥',
        '&垂直;': '⊥',
        '&三角形;': '△',
        '&圆形;': '○',
        '&正方形;': '□',
        '&长方形;': '▭',
    }

    for entity, char in math_entities.items():
        text = text.replace(entity, char)

    # 处理数字形式的实体如 &#215; (应该已经由html.unescape处理)
    # 处理 Unicode 形式如 &#x00D7; (也应该已处理)

    return text


def encode_html(text: str) -> str:
    """
    转义HTML特殊字符，防止XSS

    Args:
        text: 原始文本

    Returns:
        转义后的文本
    """
    if not text:
        return text
    return html.escape(text)
