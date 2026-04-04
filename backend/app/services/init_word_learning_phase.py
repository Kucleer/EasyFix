"""
初始化历史单词的 learning_phase
"""
from datetime import datetime, timedelta
from app.database import get_db
from app.models import Word, WordReviewLog


def init_learning_phase():
    """根据历史复习记录初始化 learning_phase"""
    db = next(get_db())

    words = db.query(Word).filter(Word.deleted == False).all()
    updated = 0

    for word in words:
        if word.review_count == 0:
            word.learning_phase = "新学"
        else:
            # 获取最近复习日志判断连续正确次数
            logs = db.query(WordReviewLog).filter(
                WordReviewLog.word_id == word.id,
                WordReviewLog.deleted == False
            ).order_by(WordReviewLog.reviewed_at.desc()).limit(10).all()

            consecutive_correct = 0
            for log in reversed(logs):
                if log.is_correct:
                    consecutive_correct += 1
                else:
                    break

            # 判断阶段
            if consecutive_correct >= 3 and (word.interval or 1) >= 7:
                word.learning_phase = "牢记"
            elif word.next_review_at and word.next_review_at <= datetime.now():
                word.learning_phase = "遗忘点"
            else:
                word.learning_phase = "在途"

            # 初始化 next_review_at（如果为空）
            if not word.next_review_at:
                word.next_review_at = datetime.now() + timedelta(days=word.interval or 1)

        updated += 1

    db.commit()
    print(f"已初始化 {updated} 个单词的 learning_phase")


if __name__ == "__main__":
    init_learning_phase()