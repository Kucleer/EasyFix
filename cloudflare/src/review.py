"""单词复习抽题与原子提交；重复提交返回既有结果，不重复增加计数。"""

import hashlib
import json
import random
from datetime import timedelta,datetime
from fastapi import APIRouter,HTTPException,Query,Request
from database import Database
from analytics import now

router=APIRouter(prefix='/api/words/review')


@router.post('/start')
async def start(request:Request,count:int=Query(25,ge=10,le=100),grade:int|None=None,word_ids:str|None=None):
    """沿用未复习、到期、低正确率、其他的抽词优先级。"""
    db=Database(request.scope['env'].DB);filters=['deleted=0'];values=[]
    ids=[int(part) for part in (word_ids or '').split(',') if part.strip().isdigit()]
    if len(ids)>100:raise HTTPException(422,'每次最多100词')
    if ids:filters.append('id IN (SELECT value FROM json_each(?))');values.append(json.dumps(ids))
    if grade:filters.append('grade=?');values.append(grade)
    rows=await db.all('SELECT id,english,chinese,review_count,correct_count,next_review_at FROM word WHERE '+' AND '.join(filters),values)
    if not rows:raise HTTPException(400,'没有可复习的单词')
    pools=[[],[],[],[]];current=now()
    for row in rows:
        if not row['review_count']:index=0
        elif row['next_review_at'] and datetime.fromisoformat(row['next_review_at'])<=current:index=1
        elif (row['correct_count'] or 0)/row['review_count']<0.6:index=2
        else:index=3
        pools[index].append(row)
    selected=[]
    for pool in pools:
        selected+=random.sample(pool,min(len(pool),count-len(selected)))
        if len(selected)>=count:break
    stamp=current.isoformat(' ')
    session=await db.first('INSERT INTO word_review(total_count,correct_count,error_count,duration,reviewed_at) VALUES(?,0,0,0,?) RETURNING id',(len(selected),stamp))
    await db.run('INSERT INTO request_record(name,value,deleted,created_at) VALUES(?,?,0,?)',('word-session:'+str(session['id']),json.dumps([row['id'] for row in selected]),stamp))
    questions=[]
    for row in selected:
        others=[item for item in rows if item['id']!=row['id']]
        options=[item['chinese'] for item in random.sample(others,3)]+[row['chinese']] if len(others)>=3 else None
        if options:random.shuffle(options)
        questions.append({'word_id':row['id'],'english':row['english'],'chinese':row['chinese'],'word_length':len(row['english']),'options':options})
    return {'session_id':session['id'],'questions':questions,'total':len(questions)}


@router.post('/submit')
async def submit(request:Request):
    """在同一 D1 事务内写入复习日志、记忆计划、练习场次与幂等结果。"""
    db=Database(request.scope['env'].DB);payload=await request.json();session_id=payload.get('session_id');results=payload.get('results',[])
    if type(session_id) is not int or not isinstance(results,list) or not 1<=len(results)<=100:raise HTTPException(422,'复习结果无效')
    for item in results:
        if type(item.get('word_id')) is not int or type(item.get('is_correct')) is not bool or item.get('review_type') not in (1,2):raise HTTPException(422,'单词或题型无效')
    ids=[item['word_id'] for item in results]
    if len(set(ids))!=len(ids):raise HTTPException(422,'重复的单词结果')
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    key='word-submit:'+str(session_id)
    previous=await db.first('SELECT value FROM request_record WHERE name=? AND deleted=0',(key,))
    if previous:
        record=json.loads(previous['value'])
        if record['fingerprint']!=fingerprint:raise HTTPException(409,'此场次已提交，请刷新练习记录')
        return record['result']
    selection=await db.first('SELECT value FROM request_record WHERE name=? AND deleted=0',('word-session:'+str(session_id),))
    if not selection or set(json.loads(selection['value']))!=set(ids):raise HTTPException(400,'场次与单词不匹配，请重新开始复习')
    words=await db.all('SELECT * FROM word WHERE deleted=0 AND id IN ('+','.join('?' for _ in ids)+')',ids)
    if len(words)!=len(ids):raise HTTPException(400,'部分单词已删除，请重新开始')
    word_map={row['id']:row for row in words};current=now();stamp=current.isoformat(' ')
    old_logs=await db.all('SELECT word_id,is_correct FROM (SELECT word_id,is_correct,ROW_NUMBER() OVER(PARTITION BY word_id ORDER BY reviewed_at DESC,id DESC) AS rn FROM word_review_log WHERE deleted=0 AND word_id IN ('+','.join('?' for _ in ids)+')) WHERE rn<=9 ORDER BY word_id,rn',ids)
    history={}
    for row in old_logs:history.setdefault(row['word_id'],[]).append(bool(row['is_correct']))
    plan=[]
    for item in results:
        word=word_map[item['word_id']];ok=item['is_correct'];interval=min((word['interval'] or 1)*2,30) if ok else 1
        consecutive=0
        for correct in reversed([ok,*history.get(word['id'],[])]):
            if not correct:break
            consecutive+=1
        phase='牢记' if ok and consecutive>=3 and interval>=7 else '遗忘点' if ok and word['next_review_at'] and datetime.fromisoformat(word['next_review_at'])<=current else '在途'
        plan.append({'id':word['id'],'correct':int(ok),'user_answer':item.get('user_answer'),'review_type':item['review_type'],'interval':interval,'phase':phase,'next':(current.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=interval)).isoformat(' ')})
    correct=sum(item['is_correct'] for item in results);accuracy=round(correct/len(results)*100,1)
    output={'total':len(results),'correct':correct,'error':len(results)-correct,'accuracy':accuracy}
    subject=await db.first('SELECT id FROM subject WHERE name=\'英语\' AND deleted=0')
    if not subject:raise HTTPException(400,'缺少英语学科')
    duration=payload.get('duration',0)
    if type(duration) is not int or duration<0:raise HTTPException(422,'复习时长无效')
    packed=json.dumps(plan,ensure_ascii=False)
    statements=[('INSERT INTO request_record(name,value,deleted,created_at) VALUES(?,?,0,?)',(key,json.dumps({'fingerprint':fingerprint,'result':output}),stamp)),
                ('UPDATE word_review SET correct_count=?,error_count=?,duration=?,reviewed_at=? WHERE id=?',(correct,len(results)-correct,duration,stamp,session_id)),
                ('INSERT INTO word_review_log(word_id,is_correct,user_answer,review_type,reviewed_at,deleted) SELECT json_extract(value,\'$.id\'),json_extract(value,\'$.correct\'),json_extract(value,\'$.user_answer\'),json_extract(value,\'$.review_type\'),?,0 FROM json_each(?)',(stamp,packed)),
                ('UPDATE word SET review_count=COALESCE(review_count,0)+1,correct_count=COALESCE(correct_count,0)+(SELECT json_extract(value,\'$.correct\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=word.id),interval=(SELECT json_extract(value,\'$.interval\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=word.id),learning_phase=(SELECT json_extract(value,\'$.phase\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=word.id),next_review_at=(SELECT json_extract(value,\'$.next\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=word.id),last_reviewed_at=?,updated_at=? WHERE deleted=0 AND id IN(SELECT json_extract(value,\'$.id\') FROM json_each(?))',(packed,packed,packed,packed,stamp,stamp,packed)),
                ('INSERT INTO practice_set(name,subject_id,source_type,question_type,total_questions,reviewed,review_count,deleted,created_at,accuracy,last_reviewed_at) VALUES(?,?,\'word\',\'original\',?,1,1,0,?,?,?)',('单词复习 '+current.strftime('%Y-%m-%d %H:%M'),subject['id'],len(results),stamp,accuracy,stamp)),
                ('INSERT INTO word_review_session(practice_set_id,session_id,total_count,correct_count,accuracy,duration,reviewed_at,word_results) VALUES(last_insert_rowid(),?,?,?,?,?,?,?)',(session_id,len(results),correct,int(accuracy),duration,stamp,json.dumps([{'word_id':item['word_id'],'is_correct':item['is_correct']} for item in results])))]
    try:await db.batch(statements)
    except Exception:
        existing=await db.first('SELECT value FROM request_record WHERE name=? AND deleted=0',(key,))
        if existing:
            record=json.loads(existing['value'])
            if record['fingerprint']==fingerprint:return record['result']
        raise HTTPException(409,'复习提交失败，请保留本页并重试')
    if len(results)>=10:
        from motivation import trigger,word_accuracy
        try:
            await trigger(db,'review_practice_set','单词练习')
            await word_accuracy(request,len(results),correct,'单词正确率'+str(accuracy)+'%')
        except HTTPException:pass
    return output
