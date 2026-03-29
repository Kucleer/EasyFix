"""
单词路由 - 管理单词的录入、复习、统计等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from typing import Optional, List
from pydantic import BaseModel
import random
from datetime import datetime
from app.database import get_db
from app.models import Word, Tag, WordReviewLog, WordReview
from app.schemas.word import (
    WordCreate, WordUpdate, WordResponse, WordListResponse,
    WordStatsResponse, ReviewSessionSubmit, ReviewStartResponse, ReviewQuestion
)

router = APIRouter(prefix="/api/words", tags=["单词"])


@router.get("", response_model=WordListResponse)
def list_words(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    grade: Optional[int] = Query(None, ge=1, le=12),
    semester: Optional[int] = Query(None, ge=1, le=2),
    tag_ids: Optional[str] = Query(None, description="标签ID，多个用逗号分隔"),
    keyword: Optional[str] = None,
    sort_by: Optional[str] = Query(None, description="排序字段：accuracy, review_count, created_at"),
    sort_order: Optional[str] = Query("desc", description="排序方向：asc, desc"),
    accuracy_min: Optional[float] = Query(None, description="正确率下限"),
    accuracy_max: Optional[float] = Query(None, description="正确率上限"),
    db: Session = Depends(get_db),
):
    """获取单词列表"""
    query = db.query(Word).filter(Word.deleted == False)

    if grade:
        query = query.filter(Word.grade == grade)
    if semester:
        query = query.filter(Word.semester == semester)
    if keyword:
        query = query.filter(
            (Word.english.contains(keyword))
            | (Word.chinese.contains(keyword))
        )
    if tag_ids:
        tag_list = [int(t.strip()) for t in tag_ids.split(',') if t.strip().isdigit()]
        if tag_list:
            from app.models.word import word_tag
            query = query.join(word_tag).filter(word_tag.c.tag_id.in_(tag_list))

    # 先获取所有匹配的数据用于计算正确率
    all_items = query.all()

    # 计算正确率并过滤
    items_with_accuracy = []
    for item in all_items:
        accuracy = (item.correct_count / item.review_count * 100) if item.review_count and item.review_count > 0 else (0 if item.review_count == 0 else None)
        items_with_accuracy.append({
            'item': item,
            'accuracy': accuracy
        })

    # 过滤正确率范围
    if accuracy_min is not None:
        items_with_accuracy = [x for x in items_with_accuracy if x['accuracy'] is not None and x['accuracy'] >= accuracy_min]
    if accuracy_max is not None:
        items_with_accuracy = [x for x in items_with_accuracy if x['accuracy'] is not None and x['accuracy'] <= accuracy_max]

    # 排序
    if sort_by == 'accuracy':
        items_with_accuracy.sort(key=lambda x: x['accuracy'] if x['accuracy'] is not None else -1, reverse=(sort_order == 'desc'))
    elif sort_by == 'review_count':
        items_with_accuracy.sort(key=lambda x: x['item'].review_count or 0, reverse=(sort_order == 'desc'))
    else:
        items_with_accuracy.sort(key=lambda x: x['item'].created_at.timestamp(), reverse=(sort_order == 'desc'))

    total = len(items_with_accuracy)

    # 应用分页
    paginated = items_with_accuracy[skip:skip + limit]
    items = [x['item'] for x in paginated]

    return {
        "total": total,
        "items": items
    }


@router.get("/{word_id}", response_model=WordResponse)
def get_word(word_id: int, db: Session = Depends(get_db)):
    """获取单词详情"""
    word = db.query(Word).filter(Word.id == word_id, Word.deleted == False).first()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")
    return word


@router.post("", response_model=WordResponse, status_code=201)
def create_word(data: WordCreate, db: Session = Depends(get_db)):
    """创建单词"""
    word = Word(
        english=data.english,
        chinese=data.chinese,
        phonetic=data.phonetic,
        grade=data.grade,
        semester=data.semester,
    )
    db.add(word)
    db.commit()
    db.refresh(word)

    # 处理标签关联
    if data.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all()
        word.tags = tags
        db.commit()
        db.refresh(word)

    return word


class WordBatchCreate(BaseModel):
    """批量创建单词"""
    words: List[dict]  # 每个对象包含 english, chinese, phonetic, grade, semester, tag_ids
    grade: Optional[int] = None
    semester: Optional[int] = None
    tag_ids: Optional[List[int]] = []


@router.post("/batch")
def batch_create_words(data: WordBatchCreate, db: Session = Depends(get_db)):
    """批量创建单词"""
    success_count = 0
    fail_count = 0
    results = []

    for word_data in data.words:
        try:
            word = Word(
                english=word_data.get('english', ''),
                chinese=word_data.get('chinese', ''),
                phonetic=word_data.get('phonetic'),
                grade=word_data.get('grade') or data.grade,
                semester=word_data.get('semester') or data.semester,
            )
            db.add(word)
            db.commit()
            db.refresh(word)

            # 处理标签
            tag_ids = word_data.get('tag_ids') or data.tag_ids
            if tag_ids:
                tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
                word.tags = tags
                db.commit()

            success_count += 1
            results.append({"english": word.english, "id": word.id, "success": True})
        except Exception as e:
            fail_count += 1
            results.append({"english": word_data.get('english', ''), "success": False, "error": str(e)})

    return {
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results
    }


@router.put("/{word_id}", response_model=WordResponse)
def update_word(word_id: int, data: WordUpdate, db: Session = Depends(get_db)):
    """更新单词"""
    word = db.query(Word).filter(Word.id == word_id, Word.deleted == False).first()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")

    update_data = data.model_dump(exclude_unset=True)
    tag_ids = update_data.pop('tag_ids', None)

    for key, value in update_data.items():
        setattr(word, key, value)

    if tag_ids is not None:
        tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
        word.tags = tags

    db.commit()
    db.refresh(word)
    return word


@router.delete("/{word_id}", status_code=204)
def delete_word(word_id: int, db: Session = Depends(get_db)):
    """删除单词（软删除）"""
    word = db.query(Word).filter(Word.id == word_id, Word.deleted == False).first()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")

    word.deleted = True
    db.commit()


@router.get("/stats/summary", response_model=WordStatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """获取单词统计"""
    # 总单词数
    total_words = db.query(Word).filter(Word.deleted == False).count()

    # 总复习次数
    total_reviews = db.query(WordReviewLog).filter(WordReviewLog.deleted == False).count()
    total_correct = db.query(WordReviewLog).filter(WordReviewLog.deleted == False, WordReviewLog.is_correct == True).count()

    # 正确率
    accuracy = (total_correct / total_reviews * 100) if total_reviews > 0 else 0

    # 各状态单词数
    mastered_words = db.query(Word).filter(
        Word.deleted == False,
        Word.review_count >= 5,
        Word.correct_count / Word.review_count >= 0.9
    ).count()

    new_words = db.query(Word).filter(
        Word.deleted == False,
        Word.review_count == 0
    ).count()

    learning_words = total_words - mastered_words - new_words

    # 今日复习数
    today = datetime.now().date()
    review_today = db.query(WordReviewLog).filter(
        WordReviewLog.deleted == False,
        func.date(WordReviewLog.reviewed_at) == today
    ).count()

    # 待复习数（超过预定复习时间）
    now = datetime.now()
    due_words = db.query(Word).filter(
        Word.deleted == False,
        Word.next_review_at != None,
        Word.next_review_at <= now
    ).count()

    # 年级分布
    grade_dist = {}
    words_by_grade = db.query(Word.grade, func.count(Word.id)).filter(
        Word.deleted == False,
        Word.grade != None
    ).group_by(Word.grade).all()
    for grade, count in words_by_grade:
        grade_dist[str(grade)] = count

    return {
        "total_words": total_words,
        "total_reviews": total_reviews,
        "total_correct": total_correct,
        "accuracy": round(accuracy, 1),
        "mastered_words": mastered_words,
        "learning_words": learning_words,
        "new_words": new_words,
        "grade_distribution": grade_dist,
        "review_today": review_today,
        "due_words": due_words,
    }


@router.post("/review/start", response_model=ReviewStartResponse)
def start_review(
    count: int = Query(25, ge=1, le=100, description="复习单词数量"),
    grade: Optional[int] = Query(None, description="按年级筛选"),
    word_ids: Optional[str] = Query(None, description="指定单词ID，多个用逗号分隔"),
    db: Session = Depends(get_db)
):
    """开始复习 - 随机抽取单词，或使用指定的单词ID"""
    query = db.query(Word).filter(Word.deleted == False)

    # 如果指定了单词ID，使用指定的单词
    if word_ids:
        id_list = [int(t.strip()) for t in word_ids.split(',') if t.strip().isdigit()]
        if id_list:
            query = query.filter(Word.id.in_(id_list))

    if grade:
        query = query.filter(Word.grade == grade)

    all_words = query.all()

    if len(all_words) == 0:
        raise HTTPException(status_code=400, detail="没有可复习的单词")

    # 随机抽取（如果指定了word_ids且数量足够，直接使用；否则随机抽）
    if word_ids and len(all_words) <= count:
        selected_words = all_words
    else:
        selected_words = random.sample(all_words, min(count, len(all_words)))

    # 创建复习场次
    review_session = WordReview(total_count=len(selected_words))
    db.add(review_session)
    db.commit()
    db.refresh(review_session)

    # 构建题目
    questions = []
    for word in selected_words:
        # 为选择题生成选项
        other_words = [w for w in all_words if w.id != word.id]
        options = None
        if len(other_words) >= 3:
            wrong_options = random.sample(other_words, 3)
            options = [w.chinese for w in wrong_options] + [word.chinese]
            random.shuffle(options)

        questions.append(ReviewQuestion(
            word_id=word.id,
            english=word.english,
            chinese=word.chinese,
            word_length=len(word.english),
            options=options
        ))

    return {
        "session_id": review_session.id,
        "questions": questions,
        "total": len(questions)
    }


@router.post("/review/submit")
def submit_review(data: ReviewSessionSubmit, db: Session = Depends(get_db)):
    """提交复习结果"""
    correct_count = 0
    error_count = 0
    now = datetime.now()

    for result in data.results:
        word = db.query(Word).filter(Word.id == result.word_id).first()
        if not word:
            continue

        # 记录复习日志
        log = WordReviewLog(
            word_id=result.word_id,
            is_correct=result.is_correct,
            user_answer=result.user_answer,
            review_type=result.review_type,
            reviewed_at=now
        )
        db.add(log)

        # 更新单词复习状态
        word.review_count = (word.review_count or 0) + 1
        if result.is_correct:
            word.correct_count = (word.correct_count or 0) + 1
            correct_count += 1
            # 更新间隔（艾宾浩斯）
            word.interval = min((word.interval or 1) * 2, 30)  # 最多30天
        else:
            error_count += 1
            word.interval = 1  # 错误后重置为1天

        # 计算下次复习时间
        word.last_reviewed_at = now
        word.next_review_at = datetime(
            now.year, now.month, now.day
        ) + timedelta(days=word.interval)

    # 更新复习场次
    review_session = db.query(WordReview).filter(WordReview.id == data.session_id).first()
    if review_session:
        review_session.correct_count = correct_count
        review_session.error_count = error_count
        review_session.duration = data.duration

    db.commit()

    return {
        "total": len(data.results),
        "correct": correct_count,
        "error": error_count,
        "accuracy": round(correct_count / len(data.results) * 100, 1) if data.results else 0
    }


@router.get("/errors", response_model=WordListResponse)
def get_error_words(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取错词列表（正确率低于60%的单词）"""
    # 子查询：获取正确率
    from sqlalchemy import case

    query = db.query(Word).filter(
        Word.deleted == False,
        Word.review_count > 0
    ).outerjoin(
        WordReviewLog, Word.id == WordReviewLog.word_id
    ).filter(
        or_(WordReviewLog.deleted == None, WordReviewLog.deleted == False)
    ).group_by(
        Word.id
    ).having(
        func.sum(case((WordReviewLog.is_correct == True, 1), else_=0)) / func.count(WordReviewLog.id) < 0.6
    )

    total = query.count()
    items = query.order_by(desc(Word.review_count)).offset(skip).limit(limit).all()

    return {"total": total, "items": items}


@router.post("/print-pdf")
def print_pdf(
    count: int = Query(25, ge=1, le=100),
    grade: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """生成单词默写PDF"""
    from app.services.pdf import generate_word_print_pdf

    query = db.query(Word).filter(Word.deleted == False)
    if grade:
        query = query.filter(Word.grade == grade)

    all_words = query.all()
    selected_words = random.sample(all_words, min(count, len(all_words)))

    # 构建数据
    words_data = [{
        "chinese": w.chinese,
        "english": w.english,
        "length": len(w.english)
    } for w in selected_words]

    pdf_path = generate_word_print_pdf("单词默写", words_data)

    return {"pdf_url": f"/uploads/{pdf_path}"}


from datetime import timedelta
