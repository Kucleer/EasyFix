from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Question, SimilarQuestion, Subject
from app.services.llm import llm_service
from app.services.logger import logger_service
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/questions", tags=["相似题"])


class BatchSimilarRequest(BaseModel):
    question_ids: List[int]


@router.post("/{question_id}/similar")
def generate_similar_question(question_id: int, db: Session = Depends(get_db)):
    """
    为指定错题生成相似题目

    Returns:
        SimilarQuestion 对象
    """
    # 只获取未删除的错题
    question = db.query(Question).filter(Question.id == question_id, Question.deleted == False).first()
    if not question:
        raise HTTPException(status_code=404, detail="错题不存在")

    if not question.original_text and not question.parsed_question:
        raise HTTPException(
            status_code=400,
            detail="错题文本为空，无法生成相似题",
        )

    # 获取学科名称
    subject_name = ""
    if question.subject:
        subject_name = question.subject.name

    # 调用LLM生成相似题
    try:
        result = llm_service.generate_similar_question(
            question=question.parsed_question or question.original_text,
            answer=question.answer or "",
            subject=subject_name,
            knowledge_point=question.knowledge_point or "",
        )
    except Exception as e:
        error_msg = str(e)
        logger_service.log_similar(
            question_id=question_id,
            similar_result={},
            success=False,
            error=error_msg,
        )
        raise HTTPException(status_code=500, detail=f"LLM调用失败: {error_msg}")

    # 检查是否有错误
    if result.get("error"):
        error_msg = result.get("error")
        logger_service.log_similar(
            question_id=question_id,
            similar_result=result,
            success=False,
            error=error_msg,
        )
        raise HTTPException(status_code=500, detail=error_msg)

    # 保存结果
    similar = SimilarQuestion(
        source_question_id=question_id,
        similar_text=result.get("similar_question", ""),
        similar_answer=result.get("similar_answer", ""),
        similarity_score=0.85,
    )
    db.add(similar)
    db.commit()
    db.refresh(similar)

    # 记录日志
    logger_service.log_similar(
        question_id=question_id,
        similar_result={
            "similar_id": similar.id,
            "similar_question": result.get("similar_question", "")[:100],
        },
        success=True,
    )

    return similar


@router.post("/batch-similar")
def batch_generate_similar(request: BatchSimilarRequest, db: Session = Depends(get_db)):
    """
    批量生成相似题目

    Args:
        request: 包含question_ids列表

    Returns:
        {
            "success_count": int,
            "failed_count": int,
            "results": [
                {"question_id": int, "similar_question_id": int or None, "error": str or None},
                ...
            ]
        }
    """
    results = []
    success_count = 0
    failed_count = 0

    for question_id in request.question_ids:
        # 获取错题
        question = db.query(Question).filter(
            Question.id == question_id,
            Question.deleted == False
        ).first()

        if not question:
            results.append({
                "question_id": question_id,
                "similar_question_id": None,
                "error": "错题不存在",
            })
            failed_count += 1
            continue

        if not question.original_text and not question.parsed_question:
            results.append({
                "question_id": question_id,
                "similar_question_id": None,
                "error": "错题文本为空",
            })
            failed_count += 1
            continue

        # 检查是否已有相似题
        existing = db.query(SimilarQuestion).filter(
            SimilarQuestion.source_question_id == question_id,
            SimilarQuestion.deleted == False
        ).first()

        if existing:
            results.append({
                "question_id": question_id,
                "similar_question_id": existing.id,
                "error": None,
            })
            success_count += 1
            continue

        # 获取学科名称
        subject_name = ""
        if question.subject:
            subject_name = question.subject.name

        # 调用LLM生成相似题
        try:
            result = llm_service.generate_similar_question(
                question=question.parsed_question or question.original_text,
                answer=question.answer or "",
                subject=subject_name,
                knowledge_point=question.knowledge_point or "",
            )
        except Exception as e:
            results.append({
                "question_id": question_id,
                "similar_question_id": None,
                "error": f"LLM调用失败: {str(e)}",
            })
            failed_count += 1
            continue

        # 检查是否有错误
        if result.get("error"):
            results.append({
                "question_id": question_id,
                "similar_question_id": None,
                "error": result.get("error"),
            })
            failed_count += 1
            continue

        # 保存结果
        try:
            similar = SimilarQuestion(
                source_question_id=question_id,
                similar_text=result.get("similar_question", ""),
                similar_answer=result.get("similar_answer", ""),
                similarity_score=0.85,
            )
            db.add(similar)
            db.commit()
            db.refresh(similar)

            results.append({
                "question_id": question_id,
                "similar_question_id": similar.id,
                "error": None,
            })
            success_count += 1

            logger_service.log_similar(
                question_id=question_id,
                similar_result={
                    "similar_id": similar.id,
                    "batch": True,
                },
                success=True,
            )
        except Exception as e:
            results.append({
                "question_id": question_id,
                "similar_question_id": None,
                "error": f"保存失败: {str(e)}",
            })
            failed_count += 1

    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
    }
