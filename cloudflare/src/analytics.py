"""学情统计：单词学情接口 /api/stats/words，以及各模块共用的北京时间 now()。

考点学情由 /api/starmap 提供（starmap.py），这里不再做知识点聚合。
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from database import Database

router = APIRouter(prefix='/api/stats')


def now():
    """返回与历史数据库一致的北京时间。"""
    return datetime.utcnow() + timedelta(hours=8)


@router.get('/words')
async def words(request: Request):
    """单词学情：正确率偏低的词（最多 20 个）和每天的复习次数（不分学科）。"""
    from question_scope import current_student_id
    db = Database(request.scope['env'].DB)
    student_id = current_student_id(request)
    low = await db.all('SELECT english AS word,ROUND(correct_count*100.0/review_count,1) AS accuracy FROM word WHERE deleted=0 AND student_id=? AND review_count>0 AND correct_count*1.0/review_count<0.7 ORDER BY id LIMIT 20',
                       (student_id,))
    # 复习日志自己没有学生列，连上单词按学生过滤
    frequency = await db.all('SELECT date(l.reviewed_at) AS date,COUNT(*) AS count FROM word_review_log l JOIN word w ON w.id=l.word_id AND w.student_id=? '
                             'WHERE l.deleted=0 GROUP BY date(l.reviewed_at) ORDER BY date', (student_id,))
    return {'low_accuracy_words': low, 'frequency': frequency}
