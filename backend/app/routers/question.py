from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
import json
from app.database import get_db
from app.models import Question, Tag, QuestionTag
from app.models.operation_log import OperationType
from app.schemas import QuestionCreate, QuestionUpdate, QuestionResponse, QuestionListResponse, QuestionBatchCreate, BatchCreateResponse
from app.services.logger import logger_service
from app.utils.html import decode_html

router = APIRouter(prefix="/api/questions", tags=["错题"])


@router.get("", response_model=QuestionListResponse)
def list_questions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    error_book_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    difficulty: Optional[str] = Query(None, description="难度，多个用逗号分隔"),
    error_type: Optional[str] = None,
    keyword: Optional[str] = None,
    grade: Optional[int] = Query(None, ge=1, le=12),
    semester: Optional[int] = Query(None, ge=1, le=2),
    tag_ids: Optional[str] = Query(None, description="标签ID，多个用逗号分隔"),
    knowledge_point: Optional[str] = Query(None, description="知识点搜索"),
    accuracy_range: Optional[str] = Query(None, description="正确率区间筛选，如 '0-30','30-60','60-80','80-100'"),
    db: Session = Depends(get_db),
):
    # 过滤已删除的记录，使用 eager loading 避免 N+1 查询
    query = db.query(Question).options(
        joinedload(Question.tags),
        joinedload(Question.similar_questions)
    ).filter(Question.deleted == False)

    if error_book_id:
        query = query.filter(Question.error_book_id == error_book_id)
    if subject_id:
        query = query.filter(Question.subject_id == subject_id)
    # 难度多选
    if difficulty:
        diff_list = [int(d.strip()) for d in difficulty.split(',') if d.strip().isdigit()]
        if diff_list:
            query = query.filter(Question.difficulty.in_(diff_list))
    if error_type:
        # 错误类型多选
        error_type_list = [e.strip() for e in error_type.split(',') if e.strip()]
        if error_type_list:
            query = query.filter(Question.error_type.in_(error_type_list))
    if grade:
        query = query.filter(Question.grade == grade)
    if semester:
        query = query.filter(Question.semester == semester)
    # 知识点搜索
    if knowledge_point:
        query = query.filter(Question.knowledge_point.contains(knowledge_point))
    if keyword:
        query = query.filter(
            (Question.original_text.contains(keyword))
            | (Question.parsed_question.contains(keyword))
            | (Question.knowledge_point.contains(keyword))
        )
    # 标签多选（通过关联表过滤）
    if tag_ids:
        tag_list = [int(t.strip()) for t in tag_ids.split(',') if t.strip().isdigit()]
        if tag_list:
            query = query.join(QuestionTag).filter(QuestionTag.c.tag_id.in_(tag_list))
    # 正确率区间筛选
    if accuracy_range:
        if accuracy_range == 'none':
            # 无统计：正确次数+错误次数都为0
            query = query.filter(
                (Question.correct_count == 0) & (Question.error_count == 0)
            )
        else:
            # 解析区间，如 '30-60'
            try:
                parts = accuracy_range.split('-')
                if len(parts) == 2:
                    min_acc = int(parts[0]) / 100
                    max_acc = int(parts[1]) / 100
                    # 正确率 = correct_count / (correct_count + error_count)
                    # 使用 SQL 表达式计算
                    from sqlalchemy import case
                    accuracy_expr = case(
                        (Question.correct_count + Question.error_count == 0, None),
                        else_=Question.correct_count * 1.0 / (Question.correct_count + Question.error_count)
                    )
                    query = query.filter(
                        (accuracy_expr >= min_acc) & (accuracy_expr <= max_acc)
                    )
            except:
                pass

    total = query.count()
    items = query.order_by(Question.created_at.desc()).offset(skip).limit(limit).all()

    # 转换items为响应格式
    result_items = []
    for q in items:
        result_items.append({
            "id": q.id,
            "error_book_id": q.error_book_id,
            "subject_id": q.subject_id,
            "original_image": q.original_image,
            "original_images": json.loads(q.original_images) if q.original_images else None,
            "original_text": q.original_text,
            "parsed_question": q.parsed_question,
            "grade": q.grade,
            "semester": q.semester,
            "answer": q.answer,
            "analysis": q.analysis,
            "difficulty": q.difficulty,
            "error_type": q.error_type,
            "knowledge_point": q.knowledge_point,
            "correct_count": q.correct_count,
            "error_count": q.error_count,
            "created_at": q.created_at,
            "updated_at": q.updated_at,
            "tags": q.tags,
            "similar_questions": q.similar_questions,
        })

    return {"total": total, "items": result_items}


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(question_id: int, db: Session = Depends(get_db)):
    # 只获取未删除的记录
    question = db.query(Question).filter(Question.id == question_id, Question.deleted == False).first()
    if not question:
        raise HTTPException(status_code=404, detail="错题不存在")
    # 转换original_images
    result = {
        "id": question.id,
        "error_book_id": question.error_book_id,
        "subject_id": question.subject_id,
        "original_image": question.original_image,
        "original_images": json.loads(question.original_images) if question.original_images else None,
        "original_text": question.original_text,
        "parsed_question": question.parsed_question,
        "grade": question.grade,
        "semester": question.semester,
        "answer": question.answer,
        "analysis": question.analysis,
        "difficulty": question.difficulty,
        "error_type": question.error_type,
        "knowledge_point": question.knowledge_point,
        "created_at": question.created_at,
        "updated_at": question.updated_at,
        "tags": question.tags,
        "similar_questions": question.similar_questions,
    }
    return result


@router.post("", response_model=QuestionResponse, status_code=201)
def create_question(data: QuestionCreate, db: Session = Depends(get_db)):
    try:
        # 处理多个图片
        original_images_json = None
        if data.original_images:
            original_images_json = json.dumps(data.original_images, ensure_ascii=False)

        question = Question(
            error_book_id=data.error_book_id,
            subject_id=data.subject_id,
            original_image=data.original_image,
            original_images=original_images_json,
            original_text=data.original_text,
            parsed_question=decode_html(data.parsed_question) if data.parsed_question else None,
            grade=data.grade,
            semester=data.semester,
            answer=decode_html(data.answer) if data.answer else None,
            analysis=decode_html(data.analysis) if data.analysis else None,
            difficulty=data.difficulty,
            error_type=data.error_type,
            knowledge_point=data.knowledge_point,
        )
        db.add(question)
        db.commit()
        db.refresh(question)

        # 触发积分行为
        from app.services.motivation import MotivationService
        try:
            service = MotivationService(db)
            service.trigger_action("upload_question", reason="上传错题")
        except Exception:
            pass  # 激励系统不影响主流程

        # 处理标签关联
        if data.tag_ids:
            tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all()
            question.tags = tags
            db.commit()

        # 记录日志
        logger_service.log_question(
            operation=OperationType.CREATE_QUESTION,
            question_id=question.id,
            data={
                "error_book_id": data.error_book_id,
                "subject_id": data.subject_id,
                "original_text": data.original_text[:100] if data.original_text else None,
            },
            success=True,
        )

        # 返回格式化的响应
        return {
            "id": question.id,
            "error_book_id": question.error_book_id,
            "subject_id": question.subject_id,
            "original_image": question.original_image,
            "original_images": json.loads(question.original_images) if question.original_images else None,
            "original_text": question.original_text,
            "parsed_question": question.parsed_question,
            "grade": question.grade,
            "semester": question.semester,
            "answer": question.answer,
            "analysis": question.analysis,
            "difficulty": question.difficulty,
            "error_type": question.error_type,
            "knowledge_point": question.knowledge_point,
            "created_at": question.created_at,
            "updated_at": question.updated_at,
            "tags": question.tags,
            "similar_questions": question.similar_questions,
        }
    except Exception as e:
        # 记录错误日志
        logger_service.log_question(
            operation=OperationType.CREATE_QUESTION,
            question_id=-1,
            data={"error_book_id": data.error_book_id, "subject_id": data.subject_id},
            success=False,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"创建错题失败: {str(e)}")


@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    data: QuestionUpdate,
    db: Session = Depends(get_db),
):
    try:
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="错题不存在")

        update_data = data.model_dump(exclude_unset=True)
        tag_ids = update_data.pop("tag_ids", None)

        # 解码HTML实体
        for key in ["parsed_question", "answer", "analysis"]:
            if key in update_data and update_data[key]:
                update_data[key] = decode_html(update_data[key])

        for key, value in update_data.items():
            setattr(question, key, value)

        if tag_ids is not None:
            tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
            question.tags = tags

        db.commit()
        db.refresh(question)

        # 记录日志
        logger_service.log_question(
            operation=OperationType.UPDATE_QUESTION,
            question_id=question_id,
            data=update_data,
            success=True,
        )

        # 返回格式化的响应
        return {
            "id": question.id,
            "error_book_id": question.error_book_id,
            "subject_id": question.subject_id,
            "original_image": question.original_image,
            "original_images": json.loads(question.original_images) if question.original_images else None,
            "original_text": question.original_text,
            "parsed_question": question.parsed_question,
            "grade": question.grade,
            "semester": question.semester,
            "answer": question.answer,
            "analysis": question.analysis,
            "analysis_image": question.analysis_image,
            "difficulty": question.difficulty,
            "error_type": question.error_type,
            "knowledge_point": question.knowledge_point,
            "created_at": question.created_at,
            "updated_at": question.updated_at,
            "tags": question.tags,
            "similar_questions": question.similar_questions,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger_service.log_question(
            operation=OperationType.UPDATE_QUESTION,
            question_id=question_id,
            data={},
            success=False,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"更新错题失败: {str(e)}")


@router.delete("/{question_id}", status_code=204)
def delete_question(question_id: int, db: Session = Depends(get_db)):
    """
    软删除错题（设置deleted=True），而非物理删除
    """
    try:
        question = db.query(Question).filter(Question.id == question_id, Question.deleted == False).first()
        if not question:
            raise HTTPException(status_code=404, detail="错题不存在")

        # 软删除：设置deleted标志为True
        question.deleted = True
        db.commit()

        # 记录日志
        logger_service.log_question(
            operation=OperationType.DELETE_QUESTION,
            question_id=question_id,
            data={"soft_delete": True},
            success=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger_service.log_question(
            operation=OperationType.DELETE_QUESTION,
            question_id=question_id,
            data={},
            success=False,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"删除错题失败: {str(e)}")


@router.post("/batch", response_model=BatchCreateResponse)
def create_questions_batch(data: QuestionBatchCreate, db: Session = Depends(get_db)):
    """
    批量创建错题（用于OCR后一道图生成多题）

    images: 多张关联图片路径
    questions: 多个题目列表
    """
    created_questions = []
    success_count = 0

    for q_data in data.questions:
        try:
            question = Question(
                error_book_id=data.error_book_id,
                subject_id=data.subject_id,
                original_images=json.dumps(data.images, ensure_ascii=False),
                original_image=data.images[0] if data.images else None,
                original_text=q_data.original_text,
                parsed_question=decode_html(q_data.parsed_question) if q_data.parsed_question else None,
                grade=data.grade,
                semester=data.semester,
                answer=decode_html(q_data.answer) if q_data.answer else None,
                analysis=decode_html(q_data.analysis) if q_data.analysis else None,
                difficulty=q_data.difficulty,
                error_type=q_data.error_type,
                knowledge_point=q_data.knowledge_point,
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            created_questions.append(question)
            success_count += 1

            logger_service.log_question(
                operation=OperationType.CREATE_QUESTION,
                question_id=question.id,
                data={"batch": True, "images": data.images},
                success=True,
            )
        except Exception as e:
            db.rollback()
            logger_service.log_question(
                operation=OperationType.CREATE_QUESTION,
                question_id=-1,
                data={"batch": True},
                success=False,
                error=str(e),
            )

    # 转换响应
    result_questions = []
    for q in created_questions:
        result_questions.append({
            "id": q.id,
            "error_book_id": q.error_book_id,
            "subject_id": q.subject_id,
            "original_image": q.original_image,
            "original_images": json.loads(q.original_images) if q.original_images else None,
            "original_text": q.original_text,
            "parsed_question": q.parsed_question,
            "answer": q.answer,
            "analysis": q.analysis,
            "difficulty": q.difficulty,
            "error_type": q.error_type,
            "knowledge_point": q.knowledge_point,
            "created_at": q.created_at,
            "updated_at": q.updated_at,
            "tags": q.tags,
            "similar_questions": q.similar_questions,
        })

    return {
        "questions": result_questions,
        "total_count": len(data.questions),
        "success_count": success_count,
    }
