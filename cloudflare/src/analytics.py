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
    db = Database(request.scope['env'].DB)
    low = await db.all('SELECT english AS word,ROUND(correct_count*100.0/review_count,1) AS accuracy FROM word WHERE deleted=0 AND review_count>0 AND correct_count*1.0/review_count<0.7 ORDER BY id LIMIT 20')
    frequency = await db.all('SELECT date(reviewed_at) AS date,COUNT(*) AS count FROM word_review_log WHERE deleted=0 GROUP BY date(reviewed_at) ORDER BY date')
    return {'low_accuracy_words': low, 'frequency': frequency}
