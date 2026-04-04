# backend/app/services/init_motivation_data.py
"""初始化激励系统预设数据"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.star import StarAction, StarRecord, StarBalance
from app.models.achievement import Achievement, AchievementProgress, AchievementConfig
from app.models.question import Question
from app.models.similar_question import SimilarQuestion
from app.models.practice_set import PracticeSet
from app.models.word import Word, WordReview


PRESET_ACTIONS = [
    {"code": "upload_question", "name": "上传错题", "star_value": 10},
    {"code": "review_practice_set", "name": "复习练习集", "star_value": 5},
    {"code": "generate_similar", "name": "生成相似题", "star_value": 3},
    {"code": "review_word", "name": "背单词", "star_value": 2},
    {"code": "create_practice_set", "name": "创建练习集", "star_value": 5},
    {"code": "daily_login", "name": "每日登录", "star_value": 1},
    {"code": "continuous_7day", "name": "连续7天学习", "star_value": 50},
    {"code": "continuous_14day", "name": "连续14天学习", "star_value": 100},
    {"code": "continuous_30day", "name": "连续30天学习", "star_value": 200},
    {"code": "review_word_accuracy", "name": "单词正确率成就", "star_value": 30},
    {"code": "manual_adjustment", "name": "手动调整", "star_value": 0},
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
    # 连续学习成就
    {"code": "continuous_learning", "name": "连续学习", "level": 1, "trigger_action": "continuous_7day", "trigger_count": 7, "reward_stars": 50, "description": "连续学习7天"},
    {"code": "continuous_learning", "name": "连续学习", "level": 2, "trigger_action": "continuous_14day", "trigger_count": 14, "reward_stars": 100, "description": "连续学习14天"},
    {"code": "continuous_learning", "name": "连续学习", "level": 3, "trigger_action": "continuous_30day", "trigger_count": 30, "reward_stars": 200, "description": "连续学习30天"},
    # 单词正确率成就
    {"code": "word_accuracy", "name": "单词正确率", "level": 1, "trigger_action": "review_word_accuracy", "trigger_count": 7, "reward_stars": 30, "description": "累计7次复习10个单词以上且正确率90%以上"},
    {"code": "word_accuracy", "name": "单词正确率", "level": 2, "trigger_action": "review_word_accuracy", "trigger_count": 14, "reward_stars": 80, "description": "累计14次复习10个单词以上且正确率90%以上"},
    {"code": "word_accuracy", "name": "单词正确率", "level": 3, "trigger_action": "review_word_accuracy", "trigger_count": 30, "reward_stars": 150, "description": "累计30次复习10个单词以上且正确率90%以上"},
]

DEFAULT_USER_ID = 1


def get_actual_count(db: Session, action_code: str) -> int:
    """根据行为代码从实际数据中获取统计数量"""
    if action_code == "upload_question":
        # 统计已上传的错题数量
        return db.query(func.count(Question.id)).filter(Question.deleted == False).scalar() or 0
    elif action_code == "review_practice_set":
        # 统计复习过的练习集次数（累计复习次数总和）
        return db.query(func.coalesce(func.sum(PracticeSet.review_count), 0)).filter(
            PracticeSet.deleted == False
        ).scalar() or 0
    elif action_code == "generate_similar":
        # 统计生成的相似题数量
        return db.query(func.count(SimilarQuestion.id)).filter(SimilarQuestion.deleted == False).scalar() or 0
    elif action_code == "review_word":
        # 统计背过的单词次数（累计复习次数总和）
        return db.query(func.coalesce(func.sum(Word.review_count), 0)).filter(
            Word.deleted == False
        ).scalar() or 0
    elif action_code == "create_practice_set":
        # 统计创建的练习集数量
        return db.query(func.count(PracticeSet.id)).filter(PracticeSet.deleted == False).scalar() or 0
    elif action_code == "daily_login":
        # 统计每日登录次数（从积分记录中获取）
        return db.query(func.count(StarRecord.id)).filter(
            StarRecord.user_id == DEFAULT_USER_ID,
            StarRecord.action_code == "daily_login"
        ).scalar() or 0
    return 0


def init_preset_data(db: Session):
    """初始化预设数据"""
    # 初始化行为
    for action_data in PRESET_ACTIONS:
        existing = db.query(StarAction).filter(StarAction.code == action_data["code"]).first()
        if not existing:
            action = StarAction(**action_data, enabled=True)
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


def init_achievement_progress(db: Session):
    """根据实际数据初始化成就进度"""
    # 获取所有预设成就
    achievements = db.query(Achievement).filter(
        Achievement.is_preset == True,
        Achievement.deleted == False
    ).all()

    for achievement in achievements:
        # 检查是否已有进度记录
        existing = db.query(AchievementProgress).filter(
            AchievementProgress.user_id == DEFAULT_USER_ID,
            AchievementProgress.achievement_id == achievement.id
        ).first()

        # 获取实际统计数量
        current_count = get_actual_count(db, achievement.trigger_action)

        if existing:
            # 更新已有进度
            existing.current_count = current_count
            # 如果达到触发条件且未解锁，则解锁
            if current_count >= achievement.trigger_count and not existing.is_unlocked:
                existing.is_unlocked = True
                from datetime import datetime
                existing.unlocked_at = datetime.now()
        else:
            # 创建新进度记录
            is_unlocked = current_count >= achievement.trigger_count
            from datetime import datetime
            progress = AchievementProgress(
                user_id=DEFAULT_USER_ID,
                achievement_id=achievement.id,
                current_count=current_count,
                is_unlocked=is_unlocked,
                unlocked_at=datetime.now() if is_unlocked else None
            )
            db.add(progress)

    db.commit()


def init_star_records_from_existing_data(db: Session):
    """根据已有练习数据初始化积分记录和余额"""
    # 检查是否已有积分记录
    existing_records = db.query(StarRecord).first()
    if existing_records:
        return  # 已有记录，不重复初始化

    # 获取所有行为配置
    actions = db.query(StarAction).filter(StarAction.enabled == True).all()
    action_map = {a.code: a for a in actions}

    total_stars = 0
    records_to_add = []

    # 上传错题 - 每个题10积分
    question_count = db.query(func.count(Question.id)).filter(Question.deleted == False).scalar() or 0
    if question_count > 0 and 'upload_question' in action_map:
        action = action_map['upload_question']
        stars = question_count * action.star_value
        total_stars += stars
        records_to_add.append(StarRecord(
            user_id=DEFAULT_USER_ID,
            action_code='upload_question',
            star_delta=stars,
            balance_after=total_stars,
            reason=f'初始化：{question_count}道错题上传奖励'
        ))

    # 复习练习集 - 使用 review_count 累计
    if 'review_practice_set' in action_map:
        action = action_map['review_practice_set']
        # 获取所有练习集的累计复习次数
        review_data = db.query(
            func.coalesce(func.sum(PracticeSet.review_count), 0)
        ).filter(PracticeSet.deleted == False).scalar() or 0
        if review_data > 0:
            stars = review_data * action.star_value
            total_stars += stars
            records_to_add.append(StarRecord(
                user_id=DEFAULT_USER_ID,
                action_code='review_practice_set',
                star_delta=stars,
                balance_after=total_stars,
                reason=f'初始化：{review_data}次练习集复习奖励'
            ))

    # 生成相似题
    similar_count = db.query(func.count(SimilarQuestion.id)).filter(SimilarQuestion.deleted == False).scalar() or 0
    if similar_count > 0 and 'generate_similar' in action_map:
        action = action_map['generate_similar']
        stars = similar_count * action.star_value
        total_stars += stars
        records_to_add.append(StarRecord(
            user_id=DEFAULT_USER_ID,
            action_code='generate_similar',
            star_delta=stars,
            balance_after=total_stars,
            reason=f'初始化：{similar_count}道相似题生成奖励'
        ))

    # 背单词 - 使用 review_count 累计
    if 'review_word' in action_map:
        action = action_map['review_word']
        review_data = db.query(
            func.coalesce(func.sum(Word.review_count), 0)
        ).filter(Word.deleted == False).scalar() or 0
        if review_data > 0:
            stars = review_data * action.star_value
            total_stars += stars
            records_to_add.append(StarRecord(
                user_id=DEFAULT_USER_ID,
                action_code='review_word',
                star_delta=stars,
                balance_after=total_stars,
                reason=f'初始化：{review_data}次单词复习奖励'
            ))

    # 创建练习集
    practice_set_count = db.query(func.count(PracticeSet.id)).filter(PracticeSet.deleted == False).scalar() or 0
    if practice_set_count > 0 and 'create_practice_set' in action_map:
        action = action_map['create_practice_set']
        stars = practice_set_count * action.star_value
        total_stars += stars
        records_to_add.append(StarRecord(
            user_id=DEFAULT_USER_ID,
            action_code='create_practice_set',
            star_delta=stars,
            balance_after=total_stars,
            reason=f'初始化：{practice_set_count}个练习集创建奖励'
        ))

    # 批量添加记录
    for record in records_to_add:
        db.add(record)

    # 更新余额
    if total_stars > 0:
        balance = db.query(StarBalance).filter(StarBalance.user_id == DEFAULT_USER_ID).first()
        if balance:
            balance.balance = total_stars
        else:
            balance = StarBalance(user_id=DEFAULT_USER_ID, balance=total_stars)
            db.add(balance)

    db.commit()


def init_achievement_configs(db: Session):
    """初始化成就配置"""
    from app.models.achievement import Achievement, AchievementConfig

    # 单词正确率成就配置（所有等级）
    word_achievements = db.query(Achievement).filter(
        Achievement.code == "word_accuracy",
        Achievement.deleted == False
    ).all()

    for word_accuracy in word_achievements:
        existing = db.query(AchievementConfig).filter(
            AchievementConfig.achievement_id == word_accuracy.id
        ).first()

        if not existing:
            config = AchievementConfig(
                achievement_id=word_accuracy.id,
                min_words=10,
                min_accuracy=90
            )
            db.add(config)

    if word_achievements:
        db.commit()