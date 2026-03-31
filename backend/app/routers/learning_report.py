from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
import json
from app.database import get_db
from app.models import LearningReport, Subject, Question, Word
from app.schemas.learning_report import (
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportListItem,
    ReportDetail,
    ReportListResponse,
)
from app.services.llm import llm_service

router = APIRouter(prefix="/api/learning-reports", tags=["学习状态分析"])


def _get_grade_name(grade: int) -> str:
    """转换年级数字为名称"""
    grade_map = {
        1: "一年级", 2: "二年级", 3: "三年级", 4: "四年级",
        5: "五年级", 6: "六年级", 7: "初一", 8: "初二",
        9: "初三", 10: "高一", 11: "高二", 12: "高三"
    }
    return grade_map.get(grade, f"{grade}年级")


def _generate_title(subject_name: Optional[str], grade: Optional[int], time_range_days: Optional[int]) -> str:
    """生成报告标题"""
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")

    parts = []
    if subject_name:
        parts.append(subject_name)
    if grade:
        parts.append(_get_grade_name(grade))
    if not parts:
        parts.append("全科")
    parts.append("学习状态分析")

    return f"{date_str}{' '.join(parts)}"


def _build_data_summary(questions: List[Question], words: List[Word]) -> dict:
    """构建数据摘要供LLM分析"""
    # 错题统计
    total_questions = len(questions)

    # 难度分布
    difficulty_dist = {}
    for q in questions:
        d = str(q.difficulty) if q.difficulty else "未知"
        difficulty_dist[d] = difficulty_dist.get(d, 0) + 1

    # 错误类型分布
    error_type_dist = {}
    for q in questions:
        if q.error_type:
            error_type_dist[q.error_type] = error_type_dist.get(q.error_type, 0) + 1

    # 知识点分布
    kp_dist = {}
    for q in questions:
        if q.knowledge_point:
            kp_dist[q.knowledge_point] = kp_dist.get(q.knowledge_point, 0) + 1

    # 复习次数分布
    review_dist = {"未复习": 0, "复习1次": 0, "复习2-5次": 0, "复习5次以上": 0}
    for q in questions:
        rc = q.review_count or 0
        if rc == 0:
            review_dist["未复习"] += 1
        elif rc == 1:
            review_dist["复习1次"] += 1
        elif rc <= 5:
            review_dist["复习2-5次"] += 1
        else:
            review_dist["复习5次以上"] += 1

    # 单词统计
    total_words = len(words)
    total_reviews = sum(w.review_count or 0 for w in words)
    total_correct = sum(w.correct_count or 0 for w in words)
    word_accuracy = (total_correct / total_reviews * 100) if total_reviews > 0 else 0

    # 低准确率单词
    low_accuracy_words = []
    for w in words:
        if w.review_count and w.review_count > 0:
            acc = (w.correct_count / w.review_count * 100) if w.review_count > 0 else 0
            if acc < 70:
                low_accuracy_words.append({
                    "word": w.english,
                    "accuracy": round(acc, 1)
                })
    low_accuracy_words.sort(key=lambda x: x["accuracy"])
    low_accuracy_words = low_accuracy_words[:10]  # 取前10

    return {
        "questions": {
            "total": total_questions,
            "difficulty_distribution": difficulty_dist,
            "error_type_distribution": error_type_dist,
            "knowledge_point_distribution": dict(sorted(kp_dist.items(), key=lambda x: x[1], reverse=True)[:20]),
            "review_distribution": review_dist,
        },
        "words": {
            "total": total_words,
            "total_reviews": total_reviews,
            "accuracy": round(word_accuracy, 1),
            "low_accuracy_words": low_accuracy_words,
        }
    }


def _calculate_overall_accuracy(questions: List[Question], words: List[Word]) -> float:
    """计算整体准确率"""
    total_count = 0
    total_correct = 0

    for q in questions:
        if q.review_count and q.review_count > 0:
            total_count += q.review_count
            total_correct += q.correct_count or 0

    for w in words:
        if w.review_count and w.review_count > 0:
            total_count += w.review_count
            total_correct += w.correct_count or 0

    if total_count == 0:
        return 0.0
    return round(total_correct / total_count * 100, 1)


@router.post("/generate", response_model=ReportGenerateResponse)
def generate_report(
    request: ReportGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    生成学习状态分析报告

    1. 根据筛选条件收集错题和单词数据
    2. 调用LLM进行多维度分析
    3. 保存报告并返回
    """
    # 验证学科存在
    subject_name = None
    if request.subject_id:
        subject = db.query(Subject).filter(
            Subject.id == request.subject_id,
            Subject.deleted == False
        ).first()
        if not subject:
            raise HTTPException(status_code=404, detail="学科不存在")
        subject_name = subject.name

    # 收集错题数据
    question_query = db.query(Question).filter(Question.deleted == False)
    if request.subject_id:
        question_query = question_query.filter(Question.subject_id == request.subject_id)
    if request.grade:
        question_query = question_query.filter(Question.grade == request.grade)
    # 时间范围过滤（按创建时间）
    if request.time_range_days:
        cutoff_date = datetime.now() - timedelta(days=request.time_range_days)
        question_query = question_query.filter(Question.created_at >= cutoff_date)
    questions = question_query.all()

    # 收集单词数据
    word_query = db.query(Word).filter(Word.deleted == False, Word.review_count > 0)
    if request.grade:
        word_query = word_query.filter(Word.grade == request.grade)
    if request.time_range_days:
        cutoff_date = datetime.now() - timedelta(days=request.time_range_days)
        word_query = word_query.filter(Word.created_at >= cutoff_date)
    words = word_query.all()

    # 检查数据量
    if len(questions) == 0 and len(words) == 0:
        raise HTTPException(
            status_code=400,
            detail="没有足够的数据生成报告，请调整筛选条件"
        )

    # 构建数据摘要
    data_summary = _build_data_summary(questions, words)

    # 生成标题
    title = request.title or _generate_title(subject_name, request.grade, request.time_range_days)

    # 调用LLM生成报告
    try:
        report_content = llm_service.generate_learning_report(
            subject_name=subject_name,
            grade=request.grade,
            time_range_days=request.time_range_days,
            data_summary=data_summary,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM调用失败: {str(e)}")

    # 计算整体准确率
    overall_accuracy = _calculate_overall_accuracy(questions, words)

    # 保存报告

    report = LearningReport(
        title=title,
        subject_id=request.subject_id,
        grade=request.grade,
        time_range_days=request.time_range_days,
        content=json.dumps(report_content, ensure_ascii=False),
        total_questions=len(questions),
        total_words=len(words),
        overall_accuracy=overall_accuracy,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return ReportGenerateResponse(id=report.id, title=title)


@router.get("/list", response_model=ReportListResponse)
def list_reports(
    skip: int = 0,
    limit: int = 20,
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取报告列表"""
    query = db.query(LearningReport).filter(LearningReport.deleted == False)

    if subject_id:
        query = query.filter(LearningReport.subject_id == subject_id)

    total = query.count()
    reports = query.order_by(LearningReport.created_at.desc()).offset(skip).limit(limit).all()

    items = []
    for report in reports:
        subject_name = None
        if report.subject:
            subject_name = report.subject.name
        items.append(ReportListItem(
            id=report.id,
            title=report.title,
            subject_id=report.subject_id,
            subject_name=subject_name,
            grade=report.grade,
            time_range_days=report.time_range_days,
            total_questions=report.total_questions,
            total_words=report.total_words,
            overall_accuracy=report.overall_accuracy,
            created_at=report.created_at,
        ))

    return ReportListResponse(total=total, items=items)


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: int, db: Session = Depends(get_db)):
    """获取报告详情"""
    report = db.query(LearningReport).filter(
        LearningReport.id == report_id,
        LearningReport.deleted == False
    ).first()

    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    subject_name = None
    if report.subject:
        subject_name = report.subject.name

    return ReportDetail(
        id=report.id,
        title=report.title,
        subject_id=report.subject_id,
        subject_name=subject_name,
        grade=report.grade,
        time_range_days=report.time_range_days,
        content=json.loads(report.content) if report.content else {},
        total_questions=report.total_questions,
        total_words=report.total_words,
        overall_accuracy=report.overall_accuracy,
        created_at=report.created_at,
    )


@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    """删除报告（软删除）"""
    report = db.query(LearningReport).filter(
        LearningReport.id == report_id,
        LearningReport.deleted == False
    ).first()

    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    report.deleted = True
    db.commit()

    return {"message": "删除成功"}
