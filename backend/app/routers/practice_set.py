"""
练习集路由 - 管理练习集的创建、打印、复习等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Form, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional, Union
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models import PracticeSet, PracticeSetQuestion, Question, SimilarQuestion, Subject, WordReviewSession
from app.models.word import WordReview, WordReviewLog, Word
from app.models.reading import ReadingPassage, ReadingQuestion
from app.services.pdf import generate_practice_set_pdf
from app.services.logger import logger_service

router = APIRouter(prefix="/api/practice-sets", tags=["练习集"])


# ============ Pydantic Schemas ============

class PracticeSetCreate(BaseModel):
    name: str
    question_ids: List[int]
    source_type: str = "question"  # question=来自错题, word=来自单词复习
    question_type: str = "original"  # original=原题, similar=相似题


class GenerateFromQuestionsRequest(BaseModel):
    """根据条件生成练习集请求"""
    subject_id: int
    grade: Optional[int] = None
    count: int = 5

    class Config:
        schema_extra = {
            "example": {
                "subject_id": 1,
                "grade": 1,
                "count": 5
            }
        }


class GenerateFromReadingRequest(BaseModel):
    """从短文生成练习集请求"""
    passage_id: int
    name: Optional[str] = None


class PracticeSetQuestionResponse(BaseModel):
    id: int
    question_id: int
    similar_question_id: Optional[int] = None
    display_order: int
    question_text: Optional[str] = None
    answer: Optional[str] = None
    phonetic: Optional[str] = None
    difficulty: Optional[int] = None
    knowledge_point: Optional[str] = None
    error_type: Optional[str] = None
    review_count: Optional[int] = 0
    is_correct: Optional[bool] = None
    user_answer: Optional[str] = None
    tags: Optional[List[dict]] = None
    # 新增：原题信息
    original_question_text: Optional[str] = None
    original_answer: Optional[str] = None
    original_image: Optional[str] = None
    # 阅读理解额外字段
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    explanation: Optional[str] = None
    is_reading_question: Optional[bool] = None

    class Config:
        from_attributes = True


class PracticeSetResponse(BaseModel):
    id: int
    name: str
    notes: Optional[str] = None
    subject_id: int
    subject_name: Optional[str] = None
    source_type: str = "question"  # question=来自错题, word=来自单词复习
    question_type: str
    pdf_path: Optional[str] = None
    total_questions: int
    reviewed: bool
    review_count: int
    accuracy: Optional[float] = None  # 整体正确率
    last_reviewed_at: Optional[datetime] = None
    review_images: Optional[List[str]] = None  # 复习图片列表
    created_at: datetime
    questions: List[PracticeSetQuestionResponse] = []
    word_review_stats: Optional[dict] = None  # 单词复习统计
    pdf_url: Optional[str] = None  # PDF下载URL

    class Config:
        from_attributes = True


class PracticeSetListResponse(BaseModel):
    total: int
    items: List[PracticeSetResponse]


class BatchSimilarRequest(BaseModel):
    question_ids: List[int]


class BatchSimilarResponse(BaseModel):
    success_count: int
    failed_count: int
    results: List[dict]


# ============ 辅助函数 ============

def get_consecutive_correct(db: Session, question_id: int) -> int:
    """获取某道题最近的连续正确次数"""
    records = db.query(PracticeSetQuestion).join(PracticeSet).filter(
        PracticeSetQuestion.question_id == question_id,
        PracticeSetQuestion.is_correct.isnot(None),
        PracticeSet.deleted == False
    ).order_by(PracticeSet.created_at.desc()).all()

    count = 0
    for r in records:
        if r.is_correct:
            count += 1
        else:
            break
    return count


# ============ 路由实现 ============

@router.post("/generate-from-questions", response_model=PracticeSetResponse, status_code=201)
def generate_practice_from_questions(data: GenerateFromQuestionsRequest, db: Session = Depends(get_db)):
    """
    根据条件生成练习集

    选择逻辑（优先级）：
    1. 未复习（review_count = 0）
    2. 需巩固（最近有错误 或 正确率 < 60%）
    3. 其他（正确率 >= 60% 且最近连续正确 < 3）
    4. 已掌握（最近连续正确 >= 3 次）
    """
    import random

    # 构建基础查询
    query = db.query(Question).filter(
        Question.subject_id == data.subject_id,
        Question.deleted == False
    )
    if data.grade:
        query = query.filter(Question.grade == data.grade)

    all_questions = query.all()

    # 分类到4个优先级池
    pool_unvisited = []   # 优先级1：未复习
    pool_need_review = [] # 优先级2：需巩固
    pool_other = []       # 优先级3：其他
    pool_mastered = []    # 优先级4：已掌握

    for q in all_questions:
        consecutive = get_consecutive_correct(db, q.id)

        if q.review_count == 0:
            pool_unvisited.append(q)
        elif consecutive >= 3:
            pool_mastered.append(q)
        elif q.error_count > 0 or (q.correct_count / q.review_count < 0.6):
            pool_need_review.append(q)
        else:
            pool_other.append(q)

    # 按优先级依次抽取
    selected_ids = []
    remaining = data.count

    for pool in [pool_unvisited, pool_need_review, pool_other, pool_mastered]:
        if remaining <= 0:
            break
        if pool:
            count = min(len(pool), remaining)
            selected = random.sample(pool, count)
            selected_ids.extend([q.id for q in selected])
            remaining -= count

    # 实际取出的数量
    actual_count = len(selected_ids)
    if actual_count == 0:
        raise HTTPException(status_code=400, detail="没有符合条件的题目")

    # 获取题目详情
    selected_questions = db.query(Question).filter(Question.id.in_(selected_ids)).all()
    # 保持优先级顺序
    question_map = {q.id: q for q in selected_questions}
    ordered_questions = [question_map[qid] for qid in selected_ids if qid in question_map]

    # 创建练习集
    practice_set = PracticeSet(
        name=f"练习集_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        subject_id=data.subject_id,
        source_type="question",
        question_type="original",
        total_questions=actual_count,
    )
    db.add(practice_set)
    db.commit()
    db.refresh(practice_set)

    # 创建关联记录
    for idx, question in enumerate(ordered_questions):
        psq = PracticeSetQuestion(
            practice_set_id=practice_set.id,
            question_id=question.id,
            display_order=idx,
        )
        db.add(psq)

    db.commit()
    db.refresh(practice_set)

    # 获取学科名称
    subject_name = db.query(Subject).filter(Subject.id == data.subject_id).first().name if data.subject_id else ""

    # 构建题目数据用于生成PDF
    questions_data = []
    for question in ordered_questions:
        questions_data.append({
            "question_text": question.parsed_question or question.original_text or "",
            "difficulty": question.difficulty or 3,
            "id": question.id,
            "knowledge_point": question.knowledge_point or "",
            "error_type": question.error_type or "",
        })

    # 生成PDF
    pdf_url = None
    if questions_data:
        try:
            pdf_path = generate_practice_set_pdf(practice_set.name, questions_data)
            practice_set.pdf_path = pdf_path
            db.commit()
            pdf_url = f"/uploads/{pdf_path}"
        except Exception as e:
            print(f"PDF生成失败: {e}")

    return {
        "id": practice_set.id,
        "name": practice_set.name,
        "subject_id": practice_set.subject_id,
        "subject_name": subject_name,
        "source_type": "question",
        "question_type": "original",
        "total_questions": actual_count,
        "reviewed": False,
        "review_count": 0,
        "pdf_path": practice_set.pdf_path,
        "created_at": practice_set.created_at,
        "questions": [],
        "pdf_url": pdf_url,
    }


@router.post("/generate-from-reading", response_model=PracticeSetResponse, status_code=201)
def generate_practice_from_reading(data: GenerateFromReadingRequest, db: Session = Depends(get_db)):
    """
    从短文生成阅读理解练习集

    创建 source_type=reading 的练习集，关联短文
    """
    from app.models.reading import ReadingPassage, ReadingQuestion

    # 验证短文存在
    passage = db.query(ReadingPassage).options(
        joinedload(ReadingPassage.questions)
    ).filter(
        ReadingPassage.id == data.passage_id,
        ReadingPassage.deleted == False
    ).first()

    if not passage:
        raise HTTPException(status_code=404, detail="短文不存在")

    if not passage.questions:
        raise HTTPException(status_code=400, detail="该短文没有选择题")

    # 创建练习集（reading 类型不创建 PracticeSetQuestion 记录，
    # 题目来自 ReadingQuestion 表，通过 passage_id 关联）
    practice_set = PracticeSet(
        name=data.name or f"阅读理解-{passage.title}"[:200],
        subject_id=_get_english_subject_id(db),
        source_type="reading",
        question_type="original",
        total_questions=len(passage.questions),
        passage_id=passage.id,
    )
    db.add(practice_set)
    db.commit()
    db.refresh(practice_set)

    subject_name = db.query(Subject).filter(Subject.id == practice_set.subject_id).first().name if practice_set.subject_id else ""

    return {
        "id": practice_set.id,
        "name": practice_set.name,
        "subject_id": practice_set.subject_id,
        "subject_name": subject_name,
        "source_type": "reading",
        "question_type": "original",
        "pdf_path": practice_set.pdf_path,
        "total_questions": len(passage.questions),
        "reviewed": False,
        "review_count": 0,
        "created_at": practice_set.created_at,
        "questions": [],
    }


def _get_english_subject_id(db: Session) -> int:
    """获取英语学科ID，如果不存在则创建"""
    from app.models.subject import Subject
    subject = db.query(Subject).filter(Subject.name == "英语").first()
    if subject:
        return subject.id
    # 创建英语学科
    subject = Subject(name="英语")
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject.id


@router.post("", response_model=PracticeSetResponse, status_code=201)
def create_practice_set(data: PracticeSetCreate, db: Session = Depends(get_db)):
    """
    创建练习集

    1. 验证所有题目存在且未删除
    2. 如果是similar类型，自动为每道题生成相似题
    3. 创建练习集和关联记录
    """
    # 验证题目
    questions = db.query(Question).filter(
        Question.id.in_(data.question_ids),
        Question.deleted == False
    ).all()

    if len(questions) != len(data.question_ids):
        raise HTTPException(status_code=400, detail="部分题目不存在或已删除")

    if not questions:
        raise HTTPException(status_code=400, detail="题目列表为空")

    # 获取学科ID（使用第一个题目的学科）
    subject_id = questions[0].subject_id

    # 如果是相似题类型，先行为每道题生成相似题
    similar_question_ids = []
    if data.question_type == "similar":
        from app.services.llm import llm_service

        for q in questions:
            # 检查是否已有相似题
            existing = db.query(SimilarQuestion).filter(
                SimilarQuestion.source_question_id == q.id,
                SimilarQuestion.deleted == False
            ).first()

            if existing:
                similar_question_ids.append((q.id, existing.id))
            else:
                # 调用LLM生成相似题
                subject_name = q.subject.name if q.subject else ""
                try:
                    result = llm_service.generate_similar_question(
                        question=q.parsed_question or q.original_text,
                        answer=q.answer or "",
                        subject=subject_name,
                        knowledge_point=q.knowledge_point or "",
                    )

                    if result.get("error"):
                        continue

                    # 保存相似题
                    similar = SimilarQuestion(
                        source_question_id=q.id,
                        similar_text=result.get("similar_question", ""),
                        similar_answer=result.get("similar_answer", ""),
                        similarity_score=0.85,
                    )
                    db.add(similar)
                    db.commit()
                    db.refresh(similar)
                    similar_question_ids.append((q.id, similar.id))
                except Exception:
                    continue

    # 创建练习集
    practice_set = PracticeSet(
        name=data.name,
        subject_id=subject_id,
        source_type=data.source_type,
        question_type=data.question_type,
        total_questions=len(data.question_ids),
    )
    db.add(practice_set)
    db.commit()
    db.refresh(practice_set)

    # 创建关联记录
    for idx, question_id in enumerate(data.question_ids):
        similar_q_id = None
        if data.question_type == "similar" and similar_question_ids:
            for q_id, sq_id in similar_question_ids:
                if q_id == question_id:
                    similar_q_id = sq_id
                    break

        psq = PracticeSetQuestion(
            practice_set_id=practice_set.id,
            question_id=question_id,
            similar_question_id=similar_q_id,
            display_order=idx,
        )
        db.add(psq)

    db.commit()
    db.refresh(practice_set)

    # 返回结果
    subject_name = db.query(Subject).filter(Subject.id == subject_id).first().name if subject_id else ""

    return {
        "id": practice_set.id,
        "name": practice_set.name,
        "subject_id": practice_set.subject_id,
        "subject_name": subject_name,
        "source_type": practice_set.source_type or "question",
        "question_type": practice_set.question_type,
        "pdf_path": practice_set.pdf_path,
        "total_questions": practice_set.total_questions,
        "reviewed": practice_set.reviewed,
        "review_count": practice_set.review_count,
        "created_at": practice_set.created_at,
        "questions": [],
    }


@router.get("", response_model=PracticeSetListResponse)
def list_practice_sets(
    skip: int = 0,
    limit: int = 20,
    subject_id: Optional[int] = None,
    reviewed: Optional[bool] = None,
    source_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取练习集列表"""
    query = db.query(PracticeSet).filter(PracticeSet.deleted == False)

    if subject_id:
        query = query.filter(PracticeSet.subject_id == subject_id)
    if reviewed is not None:
        query = query.filter(PracticeSet.reviewed == reviewed)
    if source_type:
        query = query.filter(PracticeSet.source_type == source_type)
    if start_date:
        query = query.filter(PracticeSet.created_at >= start_date)
    if end_date:
        query = query.filter(PracticeSet.created_at <= f"{end_date} 23:59:59")

    total = query.count()
    items = query.order_by(PracticeSet.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for ps in items:
        subject_name = db.query(Subject).filter(Subject.id == ps.subject_id).first().name if ps.subject_id else ""

        # 获取单词复习统计
        word_review_stats = None
        if ps.source_type == "word":
            print(f"[DEBUG] Processing word practice set id={ps.id}, name={ps.name}")
            sessions = db.query(WordReviewSession).filter(
                WordReviewSession.practice_set_id == ps.id
            ).order_by(WordReviewSession.reviewed_at.desc()).all()
            print(f"[DEBUG] Found {len(sessions)} sessions for practice_set_id={ps.id}")

            if sessions:
                total_count = sum(s.total_count for s in sessions)
                total_correct = sum(s.correct_count for s in sessions)
                total_duration = sum(getattr(s, 'duration', 0) or 0 for s in sessions)

                # 获取复习类型（从最近的复习日志中获取）
                review_type = 1  # 默认默写
                latest_session = sessions[0]  # 最近的复习场次
                if latest_session.session_id:
                    from app.models.word import WordReview
                    word_review = db.query(WordReview).filter(WordReview.id == latest_session.session_id).first()
                    if word_review:
                        # 查找该场次的复习日志
                        log = db.query(WordReviewLog).filter(
                            WordReviewLog.reviewed_at >= word_review.reviewed_at,
                            WordReviewLog.deleted == False
                        ).order_by(WordReviewLog.reviewed_at.desc()).first()
                        if log:
                            review_type = log.review_type

                word_review_stats = {
                    "total_count": total_count,
                    "correct_count": total_correct,
                    "accuracy": round(total_correct / total_count * 100, 1) if total_count > 0 else 0,
                    "duration": total_duration,
                    "review_type": review_type,
                }
                print(f"[DEBUG] word_review_stats = {word_review_stats}")

        result.append({
            "id": ps.id,
            "name": ps.name,
            "subject_id": ps.subject_id,
            "subject_name": subject_name,
            "source_type": ps.source_type or "question",
            "question_type": ps.question_type,
            "pdf_path": ps.pdf_path,
            "total_questions": ps.total_questions,
            "reviewed": ps.reviewed or False,
            "review_count": ps.review_count or 0,
            "accuracy": ps.accuracy,
            "created_at": ps.created_at,
            "questions": [],
            "word_review_stats": word_review_stats,
        })

    return {"total": total, "items": result}


@router.get("/{practice_set_id}", response_model=PracticeSetResponse)
def get_practice_set(practice_set_id: int, db: Session = Depends(get_db)):
    """获取练习集详情（含题目列表）"""
    ps = db.query(PracticeSet).filter(
        PracticeSet.id == practice_set_id,
        PracticeSet.deleted == False
    ).first()

    if not ps:
        raise HTTPException(status_code=404, detail="练习集不存在")

    subject_name = db.query(Subject).filter(Subject.id == ps.subject_id).first().name if ps.subject_id else ""

    # 解析复习图片
    review_images = None
    if ps.review_images:
        try:
            import json
            review_images = json.loads(ps.review_images)
        except:
            review_images = [ps.review_images] if ps.review_images else None

    # 获取关联的题目
    questions = []
    word_review_stats = None

    if ps.source_type == "word":
        # 单词练习集：获取复习统计和单词题目
        sessions = db.query(WordReviewSession).filter(
            WordReviewSession.practice_set_id == practice_set_id
        ).order_by(WordReviewSession.reviewed_at.desc()).all()

        if sessions:
            total_count = sum(s.total_count for s in sessions)
            total_correct = sum(s.correct_count for s in sessions)
            total_duration = sum(getattr(s, 'duration', 0) or 0 for s in sessions)

            # 获取复习类型（从最近的复习日志中获取）
            review_type = 1  # 默认默写
            latest_session = sessions[0]  # 最近的复习场次
            if latest_session.session_id:
                from app.models.word import WordReview
                word_review = db.query(WordReview).filter(WordReview.id == latest_session.session_id).first()
                if word_review:
                    log = db.query(WordReviewLog).filter(
                        WordReviewLog.reviewed_at >= word_review.reviewed_at,
                        WordReviewLog.deleted == False
                    ).order_by(WordReviewLog.reviewed_at.desc()).first()
                    if log:
                        review_type = log.review_type

            word_review_stats = {
                "total_count": total_count,
                "correct_count": total_correct,
                "accuracy": round(total_correct / total_count * 100, 1) if total_count > 0 else 0,
                "duration": total_duration,
                "reviewed_at": sessions[0].reviewed_at if sessions else None,
                "review_type": review_type,
            }

            # 获取单词题目（从 WordReviewLog 中获取，通过 reviewed_at 时间匹配）
            for idx, session in enumerate(sessions):
                review_logs = db.query(WordReviewLog).filter(
                    WordReviewLog.reviewed_at == session.reviewed_at
                ).order_by(WordReviewLog.id).all()

                for log in review_logs:
                    word = db.query(Word).filter(Word.id == log.word_id).first()
                    if not word:
                        continue
                    # 获取单词标签
                    tags = [{"id": t.id, "name": t.name} for t in word.tags] if word.tags else []
                    questions.append({
                        "id": log.id,
                        "question_id": word.id,
                        "similar_question_id": None,
                        "display_order": len(questions),
                        "question_text": word.english,
                        "answer": word.chinese,
                        "phonetic": word.phonetic,
                        "difficulty": None,
                        "is_correct": log.is_correct,
                        "user_answer": log.user_answer,
                        "tags": tags,
                    })

    if ps.source_type == "reading" and ps.passage_id:
        from app.models.reading import ReadingPassage, ReadingQuestion
        passage = db.query(ReadingPassage).options(
            joinedload(ReadingPassage.questions)
        ).filter(ReadingPassage.id == ps.passage_id).first()

        if passage:
            for idx, q in enumerate(passage.questions):
                questions.append({
                    "id": q.id,
                    "question_id": q.id,
                    "similar_question_id": None,
                    "display_order": idx,
                    "question_text": q.question_text,
                    "answer": q.correct_answer,
                    "difficulty": passage.difficulty,
                    "knowledge_point": f"阅读理解-{passage.topic}",
                    "is_correct": None,
                    "tags": [],
                    "original_question_text": q.question_text,
                    "original_answer": q.correct_answer,
                    "original_image": None,
                    # 阅读理解额外字段
                    "option_a": q.option_a,
                    "option_b": q.option_b,
                    "option_c": q.option_c,
                    "option_d": q.option_d,
                    "explanation": q.explanation,
                    "is_reading_question": True,
                })
    else:
        # 错题练习集：获取题目列表
        ps_questions = db.query(PracticeSetQuestion).filter(
            PracticeSetQuestion.practice_set_id == practice_set_id
        ).order_by(PracticeSetQuestion.display_order).all()

        for psq in ps_questions:
            question = db.query(Question).filter(Question.id == psq.question_id).first()
            if not question:
                continue

            if ps.question_type == "similar" and psq.similar_question_id:
                similar = db.query(SimilarQuestion).filter(SimilarQuestion.id == psq.similar_question_id).first()
                question_text = similar.similar_text if similar else ""
                answer = similar.similar_answer if similar else ""
            else:
                question_text = question.parsed_question or question.original_text or ""
                answer = question.answer or ""

            questions.append({
                "id": psq.id,
                "question_id": psq.question_id,
                "similar_question_id": psq.similar_question_id,
                "display_order": psq.display_order,
                "question_text": question_text,
                "answer": answer,
                "difficulty": question.difficulty,
                "knowledge_point": question.knowledge_point or "",
                "error_type": question.error_type or "",
                "review_count": question.review_count or 0,
                "is_correct": psq.is_correct,
                "original_question_text": question.parsed_question or question.original_text or "",
                "original_answer": question.answer or "",
                "original_image": question.original_image or None,
            })

    return {
        "id": ps.id,
        "name": ps.name,
        "notes": ps.notes,
        "subject_id": ps.subject_id,
        "subject_name": subject_name,
        "source_type": ps.source_type or "question",
        "question_type": ps.question_type,
        "pdf_path": ps.pdf_path,
        "total_questions": ps.total_questions,
        "reviewed": ps.reviewed,
        "review_count": ps.review_count,
        "accuracy": ps.accuracy,
        "last_reviewed_at": ps.last_reviewed_at,
        "review_images": review_images,
        "created_at": ps.created_at,
        "questions": questions,
        "word_review_stats": word_review_stats,
    }


class PracticeSetUpdateRequest(BaseModel):
    """更新练习集请求"""
    name: Optional[str] = None
    notes: Optional[str] = None


class ReviewImagesUpdateRequest(BaseModel):
    """更新复习图片请求"""
    images: Optional[List[str]] = None  # 新的图片路径列表


@router.put("/{practice_set_id}")
def update_practice_set(practice_set_id: int, data: PracticeSetUpdateRequest, db: Session = Depends(get_db)):
    """更新练习集名称和备注"""
    ps = db.query(PracticeSet).filter(
        PracticeSet.id == practice_set_id,
        PracticeSet.deleted == False
    ).first()

    if not ps:
        raise HTTPException(status_code=404, detail="练习集不存在")

    if data.name is not None:
        ps.name = data.name
    if data.notes is not None:
        ps.notes = data.notes

    db.commit()

    return {"message": "更新成功"}


@router.put("/{practice_set_id}/review-images")
def update_review_images(
    practice_set_id: int,
    data: ReviewImagesUpdateRequest,
    db: Session = Depends(get_db)
):
    """更新练习集的复习图片"""
    ps = db.query(PracticeSet).filter(
        PracticeSet.id == practice_set_id,
        PracticeSet.deleted == False
    ).first()

    if not ps:
        raise HTTPException(status_code=404, detail="练习集不存在")

    if data.images is not None:
        import json
        ps.review_images = json.dumps(data.images, ensure_ascii=False)

    db.commit()

    return {"message": "更新成功", "review_images": data.images}


@router.post("/{practice_set_id}/generate-pdf")
def generate_pdf(practice_set_id: int, db: Session = Depends(get_db)):
    """为练习集生成PDF"""
    ps = db.query(PracticeSet).filter(
        PracticeSet.id == practice_set_id,
        PracticeSet.deleted == False
    ).first()

    if not ps:
        raise HTTPException(status_code=404, detail="练习集不存在")

    questions_data = []

    # 阅读理解类型：从ReadingPassage和ReadingQuestion获取题目
    if ps.source_type == "reading" and ps.passage_id:
        passage = db.query(ReadingPassage).filter(
            ReadingPassage.id == ps.passage_id,
            ReadingPassage.deleted == False
        ).first()
        if passage:
            reading_questions = db.query(ReadingQuestion).filter(
                ReadingQuestion.passage_id == ps.passage_id,
                ReadingQuestion.deleted == False
            ).order_by(ReadingQuestion.question_number).all()

            for rq in reading_questions:
                questions_data.append({
                    "question_text": f"{rq.question_number}. {rq.question_text}",
                    "option_a": rq.option_a,
                    "option_b": rq.option_b,
                    "option_c": rq.option_c,
                    "option_d": rq.option_d,
                    "is_reading_question": True,
                    "id": rq.id,
                })
            # 保存短文标题供PDF使用
            if questions_data:
                questions_data[0]["_passage_title"] = passage.title
                questions_data[0]["_passage_content"] = passage.content
    else:
        # 普通练习集：从PracticeSetQuestion获取题目
        ps_questions = db.query(PracticeSetQuestion).filter(
            PracticeSetQuestion.practice_set_id == practice_set_id
        ).order_by(PracticeSetQuestion.display_order).all()

        for psq in ps_questions:
            question = db.query(Question).filter(Question.id == psq.question_id, Question.deleted == False).first()
            if not question:
                continue

            if ps.question_type == "similar" and psq.similar_question_id:
                similar = db.query(SimilarQuestion).filter(SimilarQuestion.id == psq.similar_question_id, SimilarQuestion.deleted == False).first()
                question_text = similar.similar_text if similar else ""
            else:
                question_text = question.parsed_question or question.original_text or ""

            questions_data.append({
                "question_text": question_text,
                "difficulty": question.difficulty or 3,
                "id": question.id,
                "knowledge_point": question.knowledge_point or "",
                "error_type": question.error_type or "",
                "review_count": question.review_count or 0,
            })

    if not questions_data:
        raise HTTPException(status_code=400, detail="练习集没有题目")

    # 生成PDF
    try:
        # 确保name是Unicode字符串
        ps_name = str(ps.name) if ps.name else "练习集"
        pdf_path = generate_practice_set_pdf(ps_name, questions_data)
        ps.pdf_path = pdf_path
        db.commit()

        logger_service.log_operation(
            operation_type="generate_pdf",
            target_type="practice_set",
            target_id=ps.id,
            data={"pdf_path": pdf_path},
            success=True,
        )

        return {"pdf_url": f"/uploads/{pdf_path}"}
    except Exception as e:
        db.rollback()
        logger_service.log_operation(
            operation_type="generate_pdf",
            target_type="practice_set",
            target_id=ps.id,
            data={},
            success=False,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"PDF生成失败: {str(e)}")


@router.post("/{practice_set_id}/mark-reviewed")
def mark_reviewed(
    practice_set_id: int,
    images: Optional[str] = Form(None),
    is_all_correct: Optional[bool] = Form(None),
    question_results: Optional[str] = Body(None),
    db: Session = Depends(get_db)
):
    """标记练习集为已复习，支持整体批改或逐题批改"""
    ps = db.query(PracticeSet).filter(
        PracticeSet.id == practice_set_id,
        PracticeSet.deleted == False
    ).first()

    if not ps:
        raise HTTPException(status_code=404, detail="练习集不存在")

    now = datetime.now()

    # 解析题目结果
    results_list = []
    if question_results:
        import json
        results_list = json.loads(question_results)

    # 更新练习集
    ps.reviewed = True
    ps.review_count += 1
    ps.last_reviewed_at = now
    if images:
        ps.review_images = images

    if ps.source_type == "reading":
        # reading 类型：直接从 question_results 计算正确率
        correct_count = sum(1 for r in results_list if r.get('is_correct'))
        total_count = len(results_list)
        if total_count > 0:
            ps.accuracy = round(correct_count / total_count * 100, 1)
        else:
            ps.accuracy = None
    else:
        # 获取所有关联题目
        ps_questions = db.query(PracticeSetQuestion).filter(
            PracticeSetQuestion.practice_set_id == practice_set_id
        ).all()

        correct_count = 0
        total_count = len(ps_questions)

        for psq in ps_questions:
            question = db.query(Question).filter(Question.id == psq.question_id).first()
            if not question:
                continue

            # 更新复习次数
            question.review_count = (question.review_count or 0) + 1

            # 根据整体批改或逐题批改更新
            if is_all_correct == True:
                # 整体全对
                psq.is_correct = True
                question.correct_count = (question.correct_count or 0) + 1
                correct_count += 1
            elif results_list:
                # 逐题批改
                result = next((r for r in results_list if r.get('question_id') == psq.question_id), None)
                if result is not None:
                    psq.is_correct = result.get('is_correct')
                    if result.get('is_correct'):
                        question.correct_count = (question.correct_count or 0) + 1
                        correct_count += 1
                    else:
                        question.error_count = (question.error_count or 0) + 1

            question.last_reviewed_at = now

        # 计算并保存整体正确率
        if total_count > 0:
            ps.accuracy = round(correct_count / total_count * 100, 1)
        else:
            ps.accuracy = None

    db.commit()

    # 触发积分行为
    from app.services.motivation import MotivationService
    try:
        service = MotivationService(db)
        service.trigger_action("review_practice_set", reason="复习练习集")
    except Exception:
        pass  # 激励系统不影响主流程

    return {"message": "已标记为复习", "review_count": ps.review_count, "accuracy": ps.accuracy}


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    ids: List[int]


@router.post("/batch-delete")
def batch_delete_practice_sets(data: BatchDeleteRequest, db: Session = Depends(get_db)):
    """批量删除练习集"""
    if not data.ids:
        raise HTTPException(status_code=400, detail="ID列表为空")

    deleted_count = db.query(PracticeSet).filter(
        PracticeSet.id.in_(data.ids),
        PracticeSet.deleted == False
    ).update({"deleted": True}, synchronize_session=False)

    db.commit()

    return {
        "success": True,
        "deleted_count": deleted_count,
        "total": len(data.ids)
    }


@router.post("/batch-download-pdf")
def batch_download_pdf(data: BatchDeleteRequest, db: Session = Depends(get_db)):
    """批量下载练习集PDF（返回PDF链接列表）"""
    if not data.ids:
        raise HTTPException(status_code=400, detail="ID列表为空")

    results = []
    for ps_id in data.ids:
        ps = db.query(PracticeSet).filter(
            PracticeSet.id == ps_id,
            PracticeSet.deleted == False
        ).first()

        if ps and ps.pdf_path:
            results.append({
                "id": ps.id,
                "name": ps.name,
                "pdf_url": f"/uploads/{ps.pdf_path}"
            })
        elif ps:
            results.append({
                "id": ps.id,
                "name": ps.name,
                "pdf_url": None,
                "error": "PDF未生成"
            })
        else:
            results.append({
                "id": ps_id,
                "pdf_url": None,
                "error": "练习集不存在"
            })

    return {"results": results}


@router.delete("/{practice_set_id}", status_code=204)
def delete_practice_set(practice_set_id: int, db: Session = Depends(get_db)):
    """删除练习集（软删除）；单词练习会回滚对应单词的复习计数"""
    ps = db.query(PracticeSet).filter(
        PracticeSet.id == practice_set_id,
        PracticeSet.deleted == False
    ).first()

    if not ps:
        raise HTTPException(status_code=404, detail="练习集不存在")

    # 单词练习：回滚单词复习计数，避免已删除练习继续计入复习统计
    if ps.source_type == "word":
        _revert_word_review_for_practice(ps, db)

    ps.deleted = True
    db.commit()


def _revert_word_review_for_practice(ps, db):
    """根据练习关联的场次记录，回滚单词 review_count/correct_count，并软删除对应日志"""
    import json
    from datetime import timedelta
    from app.models import Word, WordReviewLog

    sessions = (
        db.query(WordReviewSession)
        .filter(WordReviewSession.practice_set_id == ps.id)
        .all()
    )
    for session in sessions:
        results = []
        if session.word_results:
            try:
                results = json.loads(session.word_results)
            except Exception:
                results = []
        # 旧数据无 word_results 时，按时间窗近似回滚
        if not results:
            continue
        for item in results:
            word_id = item.get("word_id")
            is_correct = bool(item.get("is_correct"))
            if not word_id:
                continue
            word = db.query(Word).filter(Word.id == word_id).first()
            if not word:
                continue
            word.review_count = max(0, (word.review_count or 0) - 1)
            if is_correct:
                word.correct_count = max(0, (word.correct_count or 0) - 1)
            # 软删除该场次时间附近的一条匹配日志
            start = session.reviewed_at - timedelta(minutes=2)
            end = session.reviewed_at + timedelta(hours=3)
            log = (
                db.query(WordReviewLog)
                .filter(
                    WordReviewLog.word_id == word_id,
                    WordReviewLog.deleted == False,
                    WordReviewLog.reviewed_at >= start,
                    WordReviewLog.reviewed_at <= end,
                    WordReviewLog.is_correct == is_correct,
                )
                .order_by(WordReviewLog.reviewed_at.desc())
                .first()
            )
            if log:
                log.deleted = True

