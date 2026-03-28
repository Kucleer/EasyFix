from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Question, Subject, ErrorBook
from app.schemas import StatsResponse, SubjectStats, GradeStats, SemesterStats

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

        by_subject.append(
            SubjectStats(
                subject_id=subject_id,
                subject_name=subject_name,
                question_count=question_count,
                error_type_counts=error_type_counts,
                difficulty_distribution=difficulty_dist,
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

    return StatsResponse(
        total_questions=total_questions or 0,
        total_subjects=total_subjects or 0,
        total_error_books=total_error_books or 0,
        difficulty_distribution=difficulty_distribution,
        error_type_distribution=error_type_distribution,
        by_subject=by_subject,
        by_grade=by_grade,
        by_semester=by_semester,
    )