# backend/app/services/init_motivation_data.py
"""初始化激励系统预设数据"""
from sqlalchemy.orm import Session
from app.models.star import StarAction
from app.models.achievement import Achievement


PRESET_ACTIONS = [
    {"code": "upload_question", "name": "上传错题", "star_value": 10},
    {"code": "review_practice_set", "name": "复习练习集", "star_value": 5},
    {"code": "generate_similar", "name": "生成相似题", "star_value": 3},
    {"code": "review_word", "name": "背单词", "star_value": 2},
    {"code": "create_practice_set", "name": "创建练习集", "star_value": 5},
    {"code": "daily_login", "name": "每日登录", "star_value": 1},
    {"code": "continuous_7day", "name": "连续7天学习", "star_value": 50},
]


PRESET_ACHIEVEMENTS = [
    # 首次上传
    {"code": "first_upload", "name": "首次上传", "level": 1, "trigger_action": "upload_question", "trigger_count": 1, "reward_stars": 20, "description": "完成第一次错题上传"},
    # 上传达人
    {"code": "upload_master", "name": "上传达人", "level": 1, "trigger_action": "upload_question", "trigger_count": 10, "reward_stars": 50, "description": "上传10道错题"},
    {"code": "upload_master", "name": "上传达人", "level": 2, "trigger_action": "upload_question", "trigger_count": 50, "reward_stars": 100, "description": "上传50道错题"},
    {"code": "upload_master", "name": "上传达人", "level": 3, "trigger_action": "upload_question", "trigger_count": 200, "reward_stars": 200, "description": "上传200道错题"},
    # 练习高手
    {"code": "review_master", "name": "练习高手", "level": 1, "trigger_action": "review_practice_set", "trigger_count": 10, "reward_stars": 30, "description": "复习10次练习集"},
    {"code": "review_master", "name": "练习高手", "level": 2, "trigger_action": "review_practice_set", "trigger_count": 50, "reward_stars": 80, "description": "复习50次练习集"},
    {"code": "review_master", "name": "练习高手", "level": 3, "trigger_action": "review_practice_set", "trigger_count": 200, "reward_stars": 150, "description": "复习200次练习集"},
    # 单词达人
    {"code": "word_master", "name": "单词达人", "level": 1, "trigger_action": "review_word", "trigger_count": 50, "reward_stars": 50, "description": "背50个单词"},
    {"code": "word_master", "name": "单词达人", "level": 2, "trigger_action": "review_word", "trigger_count": 200, "reward_stars": 100, "description": "背200个单词"},
    {"code": "word_master", "name": "单词达人", "level": 3, "trigger_action": "review_word", "trigger_count": 500, "reward_stars": 200, "description": "背500个单词"},
    # 相似题专家
    {"code": "similar_master", "name": "相似题专家", "level": 1, "trigger_action": "generate_similar", "trigger_count": 20, "reward_stars": 60, "description": "生成20道相似题"},
    {"code": "similar_master", "name": "相似题专家", "level": 2, "trigger_action": "generate_similar", "trigger_count": 100, "reward_stars": 120, "description": "生成100道相似题"},
    {"code": "similar_master", "name": "相似题专家", "level": 3, "trigger_action": "generate_similar", "trigger_count": 300, "reward_stars": 250, "description": "生成300道相似题"},
]


def init_preset_data(db: Session):
    """初始化预设数据"""
    # 初始化行为
    for action_data in PRESET_ACTIONS:
        existing = db.query(StarAction).filter(StarAction.code == action_data["code"]).first()
        if not existing:
            action = StarAction(**action_data, is_preset=True, enabled=True)
            db.add(action)

    # 初始化成就
    for ach_data in PRESET_ACHIEVEMENTS:
        existing = db.query(Achievement).filter(
            Achievement.code == ach_data["code"],
            Achievement.level == ach_data["level"]
        ).first()
        if not existing:
            achievement = Achievement(**ach_data, is_preset=True, is_active=True)
            db.add(achievement)

    db.commit()