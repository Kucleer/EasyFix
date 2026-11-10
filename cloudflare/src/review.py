"""单词复习抽题与原子提交；重复提交返回既有结果，不重复增加计数。"""

import hashlib
import json
import random
from datetime import timedelta,datetime
from fastapi import APIRouter,HTTPException,Query,Request
from database import Database
from analytics import now
from phrase_focus import build_cells,default_spec,mixed_quota,next_level,next_phase,spec_active,split_tokens,unannotated_auto_level,unannotated_next_level
from word_focus import load_focus_context

router=APIRouter(prefix='/api/words/review')

# 复习题型：1 默写，2 选择，3 听力
REVIEW_TYPES=(1,2,3)
# 没有提交档位（旧前端）或词条未标注时使用的默认档位
DEFAULT_LEVEL=3
# 提示默写档位：每个词给首字母，不依赖重点标注
HINT_LEVEL=2
# 混合抽题（不限类型）时词组所占比例，其余为单词
PHRASE_SHARE=0.4


@router.post('/start')
async def start(request:Request,count:int=Query(25,ge=10,le=100),grade:int|None=None,word_ids:str|None=None,entry_type:str|None=Query(None,pattern='^(word|phrase)$'),dictation_level:int|None=Query(None,ge=1,le=3)):
    """沿用未复习、到期、低正确率、其他的抽词优先级；可按类型筛选并手动指定档位。"""
    db=Database(request.scope['env'].DB)
    return await start_session(db,count,grade,word_ids,entry_type,dictation_level)


def pick_by_priority(rows,count,current):
    """按 未复习 → 到期 → 正确率低于 60% → 其他 的优先级抽取最多 count 个词条。"""
    pools=[[],[],[],[]]
    for row in rows:
        if not row['review_count']:index=0
        elif row['next_review_at'] and datetime.fromisoformat(row['next_review_at'])<=current:index=1
        elif (row['correct_count'] or 0)/row['review_count']<0.6:index=2
        else:index=3
        pools[index].append(row)
    selected=[]
    for pool in pools:
        if len(selected)>=count:break
        selected+=random.sample(pool,min(len(pool),count-len(selected)))
    return selected


async def start_session(db,count,grade,word_ids,entry_type,dictation_level):
    """抽取复习题并登记场次；已标注的词组额外返回默写格子。"""
    filters=['deleted=0'];values=[]
    if entry_type is not None and entry_type not in ('word','phrase'):raise HTTPException(422,'词条类型无效')
    if dictation_level is not None and (type(dictation_level) is not int or not 1<=dictation_level<=3):raise HTTPException(422,'默写档位无效')
    ids=[int(part) for part in (word_ids or '').split(',') if part.strip().isdigit()]
    if len(ids)>100:raise HTTPException(422,'每次最多100词')
    if ids:filters.append('id IN (SELECT value FROM json_each(?))');values.append(json.dumps(ids))
    if grade:filters.append('grade=?');values.append(grade)
    if entry_type:filters.append('entry_type=?');values.append(entry_type)
    rows=await db.all('SELECT id,english,chinese,review_count,correct_count,next_review_at,entry_type,focus_spec,focus_status,focus_updated_at,dictation_level,learning_phase,grade FROM word WHERE '+' AND '.join(filters),values)
    if not rows:raise HTTPException(400,'没有可复习的单词')
    current=now()
    if entry_type is None and not ids:
        # 混合抽题：词组占 PHRASE_SHARE，其余为单词；一方不够时由另一方补足，各自仍按优先级抽
        word_rows=[row for row in rows if row['entry_type']!='phrase']
        phrase_rows=[row for row in rows if row['entry_type']=='phrase']
        word_count,phrase_count=mixed_quota(count,len(word_rows),len(phrase_rows),PHRASE_SHARE)
        selected=pick_by_priority(word_rows,word_count,current)+pick_by_priority(phrase_rows,phrase_count,current)
        # 打乱顺序，让单词和词组穿插出现
        random.shuffle(selected)
    else:
        selected=pick_by_priority(rows,count,current)
    stamp=current.isoformat(' ')
    session=await db.first('INSERT INTO word_review(total_count,correct_count,error_count,duration,reviewed_at) VALUES(?,0,0,0,?) RETURNING id',(len(selected),stamp))
    await db.run('INSERT INTO request_record(name,value,deleted,created_at) VALUES(?,?,0,?)',('word-session:'+str(session['id']),json.dumps([row['id'] for row in selected]),stamp))
    # 抽完词后一次性载入已标注词组的重点（没有已标注词组时不查询）
    context=await load_focus_context(db,selected)
    questions=[]
    for row in selected:
        others=[item for item in rows if item['id']!=row['id']]
        options=[item['chinese'] for item in random.sample(others,3)]+[row['chinese']] if len(others)>=3 else None
        if options:random.shuffle(options)
        question={'word_id':row['id'],'english':row['english'],'chinese':row['chinese'],'word_length':len(row['english']),'options':options,'entry_type':row['entry_type'],'dictation_level':DEFAULT_LEVEL}
        focus_info=context.get(row['id'])
        if focus_info:
            # 已标注词组：按存储档位（或手动指定档位）生成格子，并返回实际使用的档位
            cells,level=build_cells(focus_info['spec'],row['dictation_level'] or DEFAULT_LEVEL,dictation_level,focus_info['focus'])
            question['tokens']=cells
            question['dictation_level']=level
        elif row['entry_type']=='phrase' and len(split_tokens(row['english']))>1:
            # 未标注词组没有重点可空：自动模式按存储档位走 提示 → 完整；手动只有「提示」档生效
            wanted=dictation_level if dictation_level is not None else unannotated_auto_level(row['dictation_level'] or DEFAULT_LEVEL)
            if wanted==HINT_LEVEL:
                cells,level=build_cells(default_spec(row['english']),DEFAULT_LEVEL,HINT_LEVEL,[])
                question['tokens']=cells
                question['dictation_level']=level
        questions.append(question)
    return {'session_id':session['id'],'questions':questions,'total':len(questions)}


def validate_result_item(item):
    """校验单条复习结果的形状，不合法时抛出 422。"""
    if not isinstance(item,dict):raise HTTPException(422,'单词或题型无效')
    if type(item.get('word_id')) is not int or type(item.get('is_correct')) is not bool or item.get('review_type') not in REVIEW_TYPES:raise HTTPException(422,'单词或题型无效')
    # review_type 必须是整数本身（排除 True 等布尔值）
    if type(item.get('review_type')) is not int:raise HTTPException(422,'单词或题型无效')
    token_results=item.get('token_results')
    if token_results is not None:
        if not isinstance(token_results,list):raise HTTPException(422,'逐词结果无效')
        for entry in token_results:
            if not isinstance(entry,dict) or type(entry.get('i')) is not int or type(entry.get('ok')) is not bool:raise HTTPException(422,'逐词结果无效')
    level=item.get('dictation_level')
    if level is not None and (type(level) is not int or not 1<=level<=3):raise HTTPException(422,'默写档位无效')
    auto=item.get('dictation_auto')
    if auto is not None and type(auto) is not bool:raise HTTPException(422,'档位来源无效')


@router.post('/submit')
async def submit(request:Request):
    """提交复习结果；首次提交成功且题量足够时触发激励。"""
    db=Database(request.scope['env'].DB);payload=await request.json()
    output,first_time=await submit_session(db,payload)
    # 只有首次提交才触发激励；幂等命中不重复触发
    if first_time and len(payload['results'])>=10:
        from motivation import trigger,word_accuracy
        try:
            await trigger(db,'review_practice_set','单词练习')
            await word_accuracy(request,output['total'],output['correct'],'单词正确率'+str(output['accuracy'])+'%')
        except HTTPException:pass
    return output


async def submit_session(db,payload):
    """在同一 D1 事务内写入复习日志、记忆计划、练习场次与幂等结果；返回 (结果, 是否首次提交)。"""
    session_id=payload.get('session_id');results=payload.get('results',[])
    if type(session_id) is not int or not isinstance(results,list) or not 1<=len(results)<=100:raise HTTPException(422,'复习结果无效')
    for item in results:validate_result_item(item)
    ids=[item['word_id'] for item in results]
    if len(set(ids))!=len(ids):raise HTTPException(422,'重复的单词结果')
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    key='word-submit:'+str(session_id)
    previous=await db.first('SELECT value FROM request_record WHERE name=? AND deleted=0',(key,))
    if previous:
        record=json.loads(previous['value'])
        if record['fingerprint']!=fingerprint:raise HTTPException(409,'此场次已提交，请刷新练习记录')
        return record['result'],False
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
        # 是否到期：下次复习时间不晚于当前时间
        was_due=bool(word['next_review_at'] and datetime.fromisoformat(word['next_review_at'])<=current)
        # 已标注的词组按档位与题型决定能否「牢记」；单词与未标注词组沿用旧规则
        annotated=spec_active(word)
        level=item.get('dictation_level') or DEFAULT_LEVEL
        # 未标注的词组若以低于完整默写的档位（如提示档）作答，同样不能据此授予「牢记」，并记录档位
        tracked=annotated or (word['entry_type']=='phrase' and item['review_type']==1 and level<DEFAULT_LEVEL)
        phase=next_phase(word['learning_phase'],ok,consecutive,interval,was_due,tracked,item['review_type'],level)
        # 档位列：手动选档（dictation_auto 为假）只影响本次，不写回；缺省视为自动
        stored_level=word['dictation_level'] or DEFAULT_LEVEL
        if item.get('dictation_auto',True) is False:new_level=stored_level
        elif annotated:new_level=next_level(stored_level,ok,item['review_type'],annotated)
        # 未标注词组的默写：答对升到完整，答错从完整退回提示
        elif word['entry_type']=='phrase' and item['review_type']==1:new_level=unannotated_next_level(stored_level,ok)
        else:new_level=stored_level
        plan.append({'id':word['id'],'correct':int(ok),'user_answer':item.get('user_answer'),'review_type':item['review_type'],'interval':interval,'phase':phase,'next':(current.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=interval)).isoformat(' '),
                     # 逐词结果与日志档位只给已标注词组、以及以低档位作答的未标注词组记录，其余保持为空
                     'token_results':item.get('token_results') if tracked else None,'log_level':level if tracked else None,'word_level':new_level})
    correct=sum(item['is_correct'] for item in results);accuracy=round(correct/len(results)*100,1)
    output={'total':len(results),'correct':correct,'error':len(results)-correct,'accuracy':accuracy}
    subject=await db.first('SELECT id FROM subject WHERE name=\'英语\' AND deleted=0')
    if not subject:raise HTTPException(400,'缺少英语学科')
    duration=payload.get('duration',0)
    if type(duration) is not int or duration<0:raise HTTPException(422,'复习时长无效')
    packed=json.dumps(plan,ensure_ascii=False)
    statements=[('INSERT INTO request_record(name,value,deleted,created_at) VALUES(?,?,0,?)',(key,json.dumps({'fingerprint':fingerprint,'result':output}),stamp)),
                ('UPDATE word_review SET correct_count=?,error_count=?,duration=?,reviewed_at=? WHERE id=?',(correct,len(results)-correct,duration,stamp,session_id)),
                ('INSERT INTO word_review_log(word_id,is_correct,user_answer,review_type,reviewed_at,deleted,token_results,dictation_level) SELECT json_extract(value,\'$.id\'),json_extract(value,\'$.correct\'),json_extract(value,\'$.user_answer\'),json_extract(value,\'$.review_type\'),?,0,json_extract(value,\'$.token_results\'),json_extract(value,\'$.log_level\') FROM json_each(?)',(stamp,packed)),
                ('UPDATE word SET review_count=COALESCE(review_count,0)+1,correct_count=COALESCE(correct_count,0)+(SELECT json_extract(value,\'$.correct\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=word.id),interval=(SELECT json_extract(value,\'$.interval\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=word.id),learning_phase=(SELECT json_extract(value,\'$.phase\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=word.id),next_review_at=(SELECT json_extract(value,\'$.next\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=word.id),dictation_level=(SELECT json_extract(value,\'$.word_level\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=word.id),last_reviewed_at=?,updated_at=? WHERE deleted=0 AND id IN(SELECT json_extract(value,\'$.id\') FROM json_each(?))',(packed,packed,packed,packed,packed,stamp,stamp,packed)),
                ('INSERT INTO practice_set(name,subject_id,source_type,question_type,total_questions,reviewed,review_count,deleted,created_at,accuracy,last_reviewed_at) VALUES(?,?,\'word\',\'original\',?,1,1,0,?,?,?)',('单词复习 '+current.strftime('%Y-%m-%d %H:%M'),subject['id'],len(results),stamp,accuracy,stamp)),
                ('INSERT INTO word_review_session(practice_set_id,session_id,total_count,correct_count,accuracy,duration,reviewed_at,word_results) VALUES(last_insert_rowid(),?,?,?,?,?,?,?)',(session_id,len(results),correct,int(accuracy),duration,stamp,json.dumps([{'word_id':item['word_id'],'is_correct':item['is_correct']} for item in results])))]
    try:await db.batch(statements)
    except Exception:
        existing=await db.first('SELECT value FROM request_record WHERE name=? AND deleted=0',(key,))
        if existing:
            record=json.loads(existing['value'])
            if record['fingerprint']==fingerprint:return record['result'],False
        raise HTTPException(409,'复习提交失败，请保留本页并重试')
    return output,True
