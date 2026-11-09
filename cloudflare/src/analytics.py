"""由 D1 执行数值聚合，避免免费 Worker 中加载 ORM 与临时数据库。"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Query
from database import Database
from settings import generate_json

router = APIRouter(prefix='/api/stats')


def now():
    """返回与历史数据库一致的北京时间。"""
    return datetime.utcnow() + timedelta(hours=8)


async def grouped(db, field, grade=None, subject_id=None):
    """只允许固定字段进行分组统计。"""
    assert field in ('difficulty', 'error_type', 'knowledge_point', 'grade', 'semester')
    filters, values = ['deleted=0'], []
    for key, value in [('grade', grade), ('subject_id', subject_id)]:
        if value is not None:
            filters.append(key+'=?')
            values.append(value)
    rows = await db.all('SELECT '+field+' AS name,COUNT(*) AS count FROM question WHERE '+' AND '.join(filters)+' GROUP BY '+field, values)
    result = {}
    for row in rows:
        if row['name'] is None:
            continue
        for name in (str(row['name']).split(',') if field == 'error_type' else [str(row['name'])]):
            if name.strip():
                result[name.strip()] = result.get(name.strip(),0)+row['count']
    return result


@router.get('/summary')
async def summary(request: Request, grade: int | None = Query(None,ge=1,le=12)):
    """按原统计口径返回错题分布、学段分布与单词复习信息。"""
    db = Database(request.scope['env'].DB)
    condition, values = (' AND grade=?',[grade]) if grade is not None else ('',[])
    q = await db.first('SELECT COUNT(*) AS total,SUM(COALESCE(review_count,0)=0 OR (review_count>0 AND correct_count=0)) AS due,COUNT(DISTINCT date(created_at)) AS days FROM question WHERE deleted=0'+condition,values)
    totals = await db.first('SELECT (SELECT COUNT(*) FROM subject WHERE deleted=0) AS subjects,(SELECT COUNT(*) FROM error_book WHERE deleted=0) AS books')
    subjects = await db.all('SELECT s.id,s.name,COUNT(q.id) AS count FROM subject s JOIN question q ON q.subject_id=s.id AND q.deleted=0 WHERE s.deleted=0'+(' AND q.grade=?' if grade is not None else '')+' GROUP BY s.id,s.name',values)
    by_subject = []
    for s in subjects:
        practices = await db.first('SELECT COUNT(*) AS count FROM practice_set WHERE subject_id=? AND deleted=0',(s['id'],))
        by_subject.append({'subject_id':s['id'],'subject_name':s['name'],'question_count':s['count'],'practice_count':practices['count'],'error_type_counts':await grouped(db,'error_type',grade,s['id']),'difficulty_distribution':await grouped(db,'difficulty',grade,s['id']),'knowledge_point_counts':await grouped(db,'knowledge_point',grade,s['id'])})
    wg = await db.all('SELECT grade,COUNT(*) AS count FROM word WHERE deleted=0 AND grade IS NOT NULL GROUP BY grade')
    qg = await db.all('SELECT grade,COUNT(*) AS count FROM question WHERE deleted=0 AND grade IS NOT NULL GROUP BY grade')
    wm, qm = {r['grade']:r['count'] for r in wg}, {r['grade']:r['count'] for r in qg}
    by_grade = [{'grade':g,'question_count':qm.get(g,0),'word_count':wm.get(g,0),'difficulty_distribution':await grouped(db,'difficulty',g)} for g in sorted(set(wm)|set(qm))]
    by_semester = []
    for semester,count in (await grouped(db,'semester',grade)).items():
        rows=await db.all('SELECT difficulty,COUNT(*) AS count FROM question WHERE deleted=0 AND semester=?'+condition+' GROUP BY difficulty',[int(semester),*values])
        by_semester.append({'semester':int(semester),'question_count':count,'difficulty_distribution':{str(r['difficulty']):r['count'] for r in rows}})
    word=await db.first('SELECT COUNT(*) AS total,SUM(review_count>0) AS reviewed,SUM(next_review_at IS NULL OR next_review_at<=?) AS due FROM word WHERE deleted=0'+condition,[now().isoformat(' '),*values])
    logs=await db.first('SELECT COUNT(*) AS total,SUM(l.is_correct) AS correct FROM word_review_log l JOIN word w ON w.id=l.word_id WHERE l.deleted=0'+(' AND w.deleted=0 AND w.grade=?' if grade is not None else ''),values)
    sessions=await db.first('SELECT COUNT(*) AS total FROM word_review_session s LEFT JOIN practice_set p ON p.id=s.practice_set_id WHERE s.deleted=0 AND (s.practice_set_id IS NULL OR p.deleted=0)')
    curve=await db.all('SELECT date(l.reviewed_at) AS date,ROUND(AVG(l.is_correct)*100,1) AS accuracy FROM word_review_log l JOIN word w ON w.id=l.word_id WHERE l.deleted=0 AND l.reviewed_at>=?'+(' AND w.deleted=0 AND w.grade=?' if grade is not None else '')+' GROUP BY date(l.reviewed_at) ORDER BY date',[(now()-timedelta(days=30)).isoformat(' '),*values])
    return {'total_questions':q['total'],'total_subjects':totals['subjects'],'total_error_books':totals['books'],'active_days':q['days'],'to_review_questions':q['due'] or 0,'difficulty_distribution':await grouped(db,'difficulty',grade),'error_type_distribution':await grouped(db,'error_type',grade),'by_subject':by_subject,'by_grade':by_grade,'by_semester':by_semester,'word_stats':{'total_words':word['total'],'reviewed_words':word['reviewed'] or 0,'total_reviews':sessions['total'],'accuracy':round((logs['correct'] or 0)/logs['total']*100,1) if logs['total'] else 0,'to_review_count':word['due'] or 0,'grade_distribution':{str(k):v for k,v in wm.items()}},'word_accuracy_curve':curve,'question_accuracy_curve':[]}


async def date_stats(db,start,end,grade=None,use_last_review=False):
    """统计指定时间窗，保持练习与单词日志的来源。"""
    dates=[start.isoformat(' '),end.isoformat(' ')]
    if grade is None:
        w=await db.first('SELECT COALESCE(SUM(s.total_count),0) AS total,COALESCE(SUM(s.correct_count),0) AS correct FROM word_review_session s LEFT JOIN practice_set p ON p.id=s.practice_set_id WHERE s.deleted=0 AND s.reviewed_at>=? AND s.reviewed_at<? AND (s.practice_set_id IS NULL OR p.deleted=0)',dates)
    else:
        w=await db.first('SELECT COUNT(*) AS total,COALESCE(SUM(l.is_correct),0) AS correct FROM word_review_log l JOIN word w ON w.id=l.word_id WHERE l.deleted=0 AND w.deleted=0 AND w.grade=? AND l.reviewed_at>=? AND l.reviewed_at<?',[grade,*dates])
    field='last_reviewed_at' if use_last_review else 'created_at'
    q=await db.first('SELECT COUNT(DISTINCT pq.question_id) AS total,COALESCE(SUM(pq.is_correct),0) AS correct FROM practice_set_question pq JOIN practice_set p ON p.id=pq.practice_set_id JOIN question q ON q.id=pq.question_id WHERE p.deleted=0 AND pq.deleted=0 AND p.source_type="question" AND pq.is_correct IS NOT NULL AND p.'+field+'>=? AND p.'+field+'<?'+(' AND q.deleted=0 AND q.grade=?' if grade is not None else ''),[*dates,*([grade] if grade is not None else [])])
    return {'word_review_count':w['total'],'word_accuracy':round(w['correct']/w['total']*100,1) if w['total'] else 0,'question_review_count':q['total'],'question_accuracy':round(q['correct']/q['total']*100,1) if q['total'] else 0}


@router.get('/today')
async def today(request: Request):
    """返回今日学习统计。"""
    start=now().replace(hour=0,minute=0,second=0,microsecond=0)
    return {'today_'+key:value for key,value in (await date_stats(Database(request.scope['env'].DB),start,start+timedelta(days=1),use_last_review=True)).items()}


@router.get('/overview')
async def overview(request: Request,grade: int | None = Query(None,ge=1,le=12)):
    """返回今日和昨日的学习概览。"""
    db=Database(request.scope['env'].DB)
    start=now().replace(hour=0,minute=0,second=0,microsecond=0)
    yesterday=await date_stats(db,start-timedelta(days=1),start,grade)
    current=await date_stats(db,start,start+timedelta(days=1),grade)
    return {**{'yesterday_'+key:value for key,value in yesterday.items()},**{'today_'+key:value for key,value in current.items()}}


@router.get('/knowledge-points')
async def knowledge(request: Request,subject_id: int | None = Query(None,ge=1)):
    """按学科区分同名知识点。"""
    return await Database(request.scope['env'].DB).all('SELECT q.knowledge_point AS name,q.subject_id,s.name AS subject_name,COUNT(*) AS total,SUM(q.review_count>0) AS reviewed,COALESCE(ROUND(SUM(q.correct_count)*100.0/NULLIF(SUM(q.review_count),0),1),0) AS accuracy,SUM(q.review_count) AS total_reviews,SUM(q.error_count) AS total_errors FROM question q JOIN subject s ON s.id=q.subject_id WHERE q.deleted=0 AND s.deleted=0 AND q.knowledge_point IS NOT NULL AND q.knowledge_point!=""'+(' AND q.subject_id=?' if subject_id is not None else '')+' GROUP BY q.subject_id,s.name,q.knowledge_point ORDER BY total DESC',[subject_id] if subject_id is not None else [])


@router.get('/analysis/full')
async def full(request: Request,subject_id: int | None = Query(None,ge=1)):
    """用数据库聚合生成完整分析，避免 ORM 初始化开销。"""
    db=Database(request.scope['env'].DB)
    condition,values=(' AND subject_id=?',[subject_id]) if subject_id is not None else ('',[])
    q=await db.first('SELECT COUNT(*) AS total,SUM(COALESCE(review_count,0)=0) AS none,SUM(review_count=1) AS once,SUM(review_count>1) AS multiple FROM question WHERE deleted=0'+condition,values)
    kps=await knowledge(request,subject_id)
    qcurve=await db.all('SELECT date(p.created_at) AS date,SUM(pq.is_correct) AS correct,COUNT(*) AS total FROM practice_set_question pq JOIN practice_set p ON p.id=pq.practice_set_id WHERE p.deleted=0 AND pq.deleted=0 AND p.source_type="question" AND p.reviewed=1 AND pq.is_correct IS NOT NULL'+(' AND p.subject_id=?' if subject_id is not None else '')+' GROUP BY date(p.created_at) ORDER BY date',values)
    correct,total=0,0
    for row in qcurve:
        correct+=row.pop('correct') or 0
        total+=row.pop('total') or 0
        row['accuracy']=round(correct/total*100,1) if total else 0
    subject=await db.first('SELECT name FROM subject WHERE id=? AND deleted=0',(subject_id,)) if subject_id else None
    include_words=subject_id is None or subject and '英' in subject['name']
    w=await db.first('SELECT COUNT(*) AS total,SUM(COALESCE(review_count,0)=0) AS unmastered,SUM(review_count>0 AND review_count<=3) AS learning,SUM(review_count>3) AS mastered,SUM(next_review_at IS NOT NULL AND next_review_at<=?) AS due FROM word WHERE deleted=0',(now().isoformat(' '),)) if include_words else {'total':0,'unmastered':0,'learning':0,'mastered':0,'due':0}
    low=await db.all('SELECT english AS word,ROUND(correct_count*100.0/review_count,1) AS accuracy FROM word WHERE deleted=0 AND review_count>0 AND correct_count*1.0/review_count<0.7 ORDER BY id LIMIT 20') if include_words else []
    frequency=await db.all('SELECT date(reviewed_at) AS date,COUNT(*) AS count FROM word_review_log WHERE deleted=0 GROUP BY date(reviewed_at) ORDER BY date') if include_words else []
    practices=await db.first('SELECT COUNT(*) AS total FROM practice_set WHERE deleted=0'+condition,values)
    weekdays=await db.all('SELECT strftime("%w",created_at) AS day,COUNT(*) AS count FROM practice_set WHERE deleted=0'+condition+' GROUP BY day',values)
    pcurve=await db.all('SELECT date(reviewed_at) AS date,total_count,correct_count FROM word_review WHERE deleted=0 ORDER BY reviewed_at')
    correct,total=0,0
    for row in pcurve:
        correct+=row.pop('correct_count') or 0
        total+=row.pop('total_count') or 0
        row['accuracy']=round(correct/total*100,1) if total else 0
    graph=await db.all('SELECT k.id,k.name,k.subject_id AS category,COUNT(q.id) AS error_count FROM knowledge_point k LEFT JOIN question q ON q.knowledge_point=k.name AND q.subject_id=k.subject_id AND q.deleted=0 WHERE k.deleted=0'+(' AND k.subject_id=?' if subject_id is not None else '')+' GROUP BY k.id,k.name,k.subject_id',values)
    for row in graph: row['id']=str(row['id'])
    return {'question_stats':{'total':q['total'],'by_difficulty':await grouped(db,'difficulty',subject_id=subject_id),'by_error_type':await grouped(db,'error_type',subject_id=subject_id),'top_error_knowledge_points':[{'point':k['name'],'subject_id':k['subject_id'],'subject_name':k['subject_name'],'count':k['total']} for k in kps],'review_effectiveness':{'not_reviewed':q['none'] or 0,'reviewed_once':q['once'] or 0,'reviewed_multiple':q['multiple'] or 0},'accuracy_trend':qcurve},'word_stats':{'total':w['total'],'mastery_distribution':{key:w[key] or 0 for key in ('unmastered','learning','mastered')},'low_accuracy_words':low,'memory_curve_status':{'due_review':w['due'] or 0,'on_track':w['total']-(w['due'] or 0)},'frequency_trend':frequency},'practice_stats':{'total_practices':practices['total'],'frequency_heatmap':{['周日','周一','周二','周三','周四','周五','周六'][int(row['day'])]:row['count'] for row in weekdays},'accuracy_trend':pcurve},'knowledge_graph':{'nodes':graph,'edges':[]}}


@router.post('/analysis/llm')
async def llm(request: Request,subject_id: int | None = Query(None,ge=1)):
    """配置的模型只解释真实统计并生成建议。"""
    import json
    stats=await full(request,subject_id)
    return await generate_json(request,'根据真实学习统计生成JSON分析，不编造数值。返回weak_points数组（point,reason,suggestion），trends对象（pattern,cause,prediction），suggestions数组（type,content,priority），learning_plan对象（daily_time,focus_areas,priority_order）。统计：'+json.dumps(stats,ensure_ascii=False))
