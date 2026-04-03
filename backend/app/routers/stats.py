from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer
from app.database import get_db
from app.models import Question, Subject, ErrorBook, Word, WordReviewLog, PracticeSet, PracticeSetQuestion
from app.schemas import StatsResponse, SubjectStats, GradeStats, SemesterStats, WordStats, AccuracyCurvePoint
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/stats", tags=["统计"])


@router.get("/summary", response_model=StatsResponse)
def get_stats_summary(db: Session = Depends(get_db)):
    """
    获取统计概览（只统计未删除的记录）

    统计维度：
    - 总错题数（排除deleted=True的）
    - 总学科数（排除deleted=True的）
    - 总错题本数（排除deleted=True的）
    - 难度分布、错误类型分布
    - 按学科/年级/学期统计
    - 单词统计
    """
    # 只统计未删除的记录
    total_questions = db.query(func.count(Question.id)).filter(Question.deleted == False).scalar()
    total_subjects = db.query(func.count(Subject.id)).filter(Subject.deleted == False).scalar()
    total_error_books = db.query(func.count(ErrorBook.id)).filter(ErrorBook.deleted == False).scalar()

    # 难度分布（只统计未删除的错题）
    difficulty_query = (
        db.query(Question.difficulty, func.count(Question.id))
        .filter(Question.deleted == False)
        .group_by(Question.difficulty)
        .all()
    )
    difficulty_distribution = {str(k): v for k, v in difficulty_query}

    # 错误类型分布（只统计未删除的错题）
    error_type_query = (
        db.query(Question.error_type, func.count(Question.id))
        .filter(Question.deleted == False, Question.error_type.isnot(None))
        .group_by(Question.error_type)
        .all()
    )
    error_type_distribution = {k: v for k, v in error_type_query}

    # 按学科统计（只统计未删除的学科和错题）
    subject_query = (
        db.query(Subject.id, Subject.name, func.count(Question.id))
        .join(Question, Subject.id == Question.subject_id)
        .filter(Subject.deleted == False, Question.deleted == False)
        .group_by(Subject.id, Subject.name)
        .all()
    )

    by_subject = []
    for subject_id, subject_name, question_count in subject_query:
        # 各错误类型统计
        error_counts = (
            db.query(Question.error_type, func.count(Question.id))
            .filter(
                Question.subject_id == subject_id,
                Question.deleted == False,
                Question.error_type.isnot(None),
            )
            .group_by(Question.error_type)
            .all()
        )
        error_type_counts = {k: v for k, v in error_counts}

        # 各难度统计
        difficulty_counts = (
            db.query(Question.difficulty, func.count(Question.id))
            .filter(Question.subject_id == subject_id, Question.deleted == False)
            .group_by(Question.difficulty)
            .all()
        )
        difficulty_dist = {str(k): v for k, v in difficulty_counts}

        # 知识点统计
        kp_counts = (
            db.query(Question.knowledge_point, func.count(Question.id))
            .filter(
                Question.subject_id == subject_id,
                Question.deleted == False,
                Question.knowledge_point.isnot(None),
            )
            .group_by(Question.knowledge_point)
            .all()
        )
        knowledge_point_counts = {k: v for k, v in kp_counts if k}

        # 练习次数（该学科下的练习集生成次数）
        practice_count = db.query(func.count(PracticeSet.id)).filter(
            PracticeSet.subject_id == subject_id,
            PracticeSet.deleted == False
        ).scalar() or 0

        by_subject.append(
            SubjectStats(
                subject_id=subject_id,
                subject_name=subject_name,
                question_count=question_count,
                error_type_counts=error_type_counts,
                difficulty_distribution=difficulty_dist,
                knowledge_point_counts=knowledge_point_counts,
                practice_count=practice_count,
            )
        )

    # 按年级统计（只统计未删除的错题）
    by_grade = []
    grade_query = (
        db.query(Question.grade, func.count(Question.id))
        .filter(Question.deleted == False, Question.grade.isnot(None))
        .group_by(Question.grade)
        .all()
    )
    for grade, question_count in grade_query:
        difficulty_counts = (
            db.query(Question.difficulty, func.count(Question.id))
            .filter(Question.grade == grade, Question.deleted == False)
            .group_by(Question.difficulty)
            .all()
        )
        difficulty_dist = {str(k): v for k, v in difficulty_counts}
        by_grade.append(GradeStats(grade=grade, question_count=question_count, difficulty_distribution=difficulty_dist))

    # 按学期统计（只统计未删除的错题）
    by_semester = []
    semester_query = (
        db.query(Question.semester, func.count(Question.id))
        .filter(Question.deleted == False, Question.semester.isnot(None))
        .group_by(Question.semester)
        .all()
    )
    for semester, question_count in semester_query:
        difficulty_counts = (
            db.query(Question.difficulty, func.count(Question.id))
            .filter(Question.semester == semester, Question.deleted == False)
            .group_by(Question.difficulty)
            .all()
        )
        difficulty_dist = {str(k): v for k, v in difficulty_counts}
        by_semester.append(SemesterStats(semester=semester, question_count=question_count, difficulty_distribution=difficulty_dist))

    # 单词统计
    total_words = db.query(func.count(Word.id)).filter(Word.deleted == False).scalar() or 0
    reviewed_words = db.query(func.count(Word.id)).filter(Word.deleted == False, Word.review_count > 0).scalar() or 0
    # 复习次数：统计word_review_log中不同reviewed_at的数量（同一时间算1次）
    total_reviews = db.query(func.count(func.distinct(WordReviewLog.reviewed_at))).filter(WordReviewLog.deleted == False).scalar() or 0

    # 计算已复习单词的正确率
    if reviewed_words > 0:
        total_correct = db.query(func.sum(Word.correct_count)).filter(Word.deleted == False, Word.review_count > 0).scalar() or 0
        total_review_count = db.query(func.sum(Word.review_count)).filter(Word.deleted == False, Word.review_count > 0).scalar() or 0
        word_accuracy = (total_correct / total_review_count * 100) if total_review_count > 0 else 0
    else:
        word_accuracy = 0

    word_stats = WordStats(
        total_words=total_words,
        reviewed_words=reviewed_words,
        total_reviews=total_reviews,
        accuracy=round(word_accuracy, 1),
    )

    # 单词准确率曲线（累计到当天的正确率）
    # 获取所有未删除的复习记录，按日期分组计算累计正确率
    all_logs = (
        db.query(
            func.date(WordReviewLog.reviewed_at).label('date'),
            func.sum(func.cast(WordReviewLog.is_correct, Integer)).label('correct'),
            func.count(WordReviewLog.id).label('total')
        )
        .filter(WordReviewLog.deleted == False)
        .group_by(func.date(WordReviewLog.reviewed_at))
        .order_by(func.date(WordReviewLog.reviewed_at))
        .all()
    )

    # 计算累计正确率
    cumulative_correct = 0
    cumulative_total = 0
    word_accuracy_curve = []
    for log in all_logs:
        cumulative_correct += log.correct or 0
        cumulative_total += log.total or 0
        accuracy = (cumulative_correct / cumulative_total * 100) if cumulative_total > 0 else 0
        word_accuracy_curve.append(AccuracyCurvePoint(
            date=log.date.strftime('%Y-%m-%d') if hasattr(log.date, 'strftime') else str(log.date),
            accuracy=round(accuracy, 1)
        ))

    # 计算活跃学习天数（从question或word_review_log最早记录到现在）
    active_days = 0
    first_question_date = db.query(func.min(Question.created_at)).filter(Question.deleted == False).scalar()
    first_review_date = db.query(func.min(WordReviewLog.reviewed_at)).filter(WordReviewLog.deleted == False).scalar()

    earliest_date = None
    if first_question_date:
        earliest_date = first_question_date
    if first_review_date:
        if earliest_date is None or first_review_date < earliest_date:
            earliest_date = first_review_date

    if earliest_date:
        active_days = (datetime.now() - earliest_date).days + 1

    return StatsResponse(
        total_questions=total_questions or 0,
        total_subjects=total_subjects or 0,
        total_error_books=total_error_books or 0,
        active_days=active_days,
        difficulty_distribution=difficulty_distribution,
        error_type_distribution=error_type_distribution,
        by_subject=by_subject,
        by_grade=by_grade,
        by_semester=by_semester,
        word_stats=word_stats,
        word_accuracy_curve=word_accuracy_curve,
    )