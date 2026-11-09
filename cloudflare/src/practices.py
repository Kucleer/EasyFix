"""练习集创建、批改和软删除，保留题目关联与单词复习明细。"""

import json
import random
from fastapi import APIRouter,HTTPException,Query,Request
from database import Database
from analytics import now

router=APIRouter(prefix='/api/practice-sets')


async def word_stats(db,practice_id):
    """聚合单词练习的原始场次信息。"""
    row=await db.first('SELECT SUM(total_count) AS total_count,SUM(correct_count) AS correct_count,SUM(duration) AS duration,MAX(reviewed_at) AS reviewed_at FROM word_review_session WHERE deleted=0 AND practice_set_id=?',(practice_id,))
    if not row or not row['total_count']: return None
    row['accuracy']=round((row['correct_count'] or 0)/row['total_count']*100,1)
    log=await db.first('SELECT review_type FROM word_review_log WHERE reviewed_at=? AND deleted=0 ORDER BY id DESC LIMIT 1',(row['reviewed_at'],))
    row['review_type']=log['review_type'] if log else 1
    return row


async def get(db,practice_id,details=True):
    """返回练习集详情，阅读、单词与错题来源分别处理。"""
    row=await db.first('SELECT p.*,s.name AS subject_name FROM practice_set p LEFT JOIN subject s ON s.id=p.subject_id AND s.deleted=0 WHERE p.id=? AND p.deleted=0',(practice_id,))
    if not row: raise HTTPException(404,'练习集不存在')
    row['reviewed']=bool(row['reviewed'])
    row['review_images']=json.loads(row['review_images']) if row['review_images'] else None
    row['questions']=[]
    row['word_review_stats']=await word_stats(db,practice_id) if row['source_type']=='word' else None
    if not details:return row
    if row['source_type']=='reading' and row['passage_id']:
        passage=await db.first('SELECT * FROM reading_passage WHERE id=? AND deleted=0',(row['passage_id'],))
        if passage:
            row['passage']=passage
            for item in await db.all('SELECT * FROM reading_question WHERE passage_id=? AND deleted=0 ORDER BY question_number',(row['passage_id'],)):
                row['questions'].append({'id':item['id'],'question_id':item['id'],'display_order':item['question_number']-1,'question_text':item['question_text'],'answer':item['correct_answer'],'original_question_text':item['question_text'],'original_answer':item['correct_answer'],'difficulty':passage['difficulty'],'knowledge_point':'阅读理解-'+passage['topic'],'is_correct':None,'is_reading_question':True,'tags':[],**{key:item[key] for key in ('option_a','option_b','option_c','option_d','explanation')}})
    elif row['source_type']=='word':
        logs=await db.all('SELECT l.*,w.english,w.chinese,w.phonetic FROM word_review_session s JOIN word_review_log l ON l.reviewed_at=s.reviewed_at AND l.deleted=0 JOIN word w ON w.id=l.word_id AND w.deleted=0 WHERE s.deleted=0 AND s.practice_set_id=? ORDER BY l.id',(practice_id,))
        row['questions']=[{'id':item['id'],'question_id':item['word_id'],'display_order':index,'question_text':item['english'],'answer':item['chinese'],'phonetic':item['phonetic'],'is_correct':bool(item['is_correct']),'user_answer':item['user_answer'],'tags':[]} for index,item in enumerate(logs)]
    else:
        rows=await db.all('SELECT pq.*,q.parsed_question,q.original_text,q.answer,q.difficulty,q.knowledge_point,q.error_type,q.review_count,q.original_image,s.similar_text,s.similar_answer FROM practice_set_question pq JOIN question q ON q.id=pq.question_id AND q.deleted=0 LEFT JOIN similar_question s ON s.id=pq.similar_question_id AND s.deleted=0 WHERE pq.deleted=0 AND pq.practice_set_id=? ORDER BY pq.display_order',(practice_id,))
        for item in rows:
            original=item['parsed_question'] or item['original_text'] or ''
            item['original_question_text']=original
            item['original_answer']=item['answer']
            item['question_text']=item['similar_text'] if row['question_type']=='similar' and item['similar_question_id'] else original
            if row['question_type']=='similar' and item['similar_question_id']:item['answer']=item['similar_answer']
            item['is_correct']=bool(item['is_correct']) if item['is_correct'] is not None else None
            row['questions'].append(item)
    return row


@router.get('')
async def listing(request:Request,skip:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=1000),subject_id:int|None=None,reviewed:bool|None=None,source_type:str|None=None,start_date:str|None=None,end_date:str|None=None):
    """按来源、学科和日期分页读取练习。"""
    db=Database(request.scope['env'].DB)
    conditions,values=['p.deleted=0'],[]
    for key,value in [('subject_id',subject_id),('reviewed',reviewed),('source_type',source_type)]:
        if value is not None:conditions.append('p.'+key+'=?');values.append(value)
    if start_date:conditions.append('p.created_at>=?');values.append(start_date)
    if end_date:conditions.append('p.created_at<=?');values.append(end_date+' 23:59:59')
    where=' AND '.join(conditions)
    total=await db.first('SELECT COUNT(*) AS total FROM practice_set p WHERE '+where,values)
    rows=await db.all('SELECT p.*,s.name AS subject_name FROM practice_set p LEFT JOIN subject s ON s.id=p.subject_id AND s.deleted=0 WHERE '+where+' ORDER BY p.created_at DESC,p.id DESC LIMIT ? OFFSET ?',[*values,limit,skip])
    sessions=await db.all('SELECT practice_set_id,SUM(total_count) AS total_count,SUM(correct_count) AS correct_count,SUM(duration) AS duration,MAX(reviewed_at) AS reviewed_at FROM word_review_session WHERE deleted=0 AND practice_set_id IN (SELECT id FROM practice_set WHERE deleted=0) GROUP BY practice_set_id')
    session_map={item['practice_set_id']:item for item in sessions}
    for row in rows:
        row['reviewed']=bool(row['reviewed']);row['questions']=[]
        row['review_images']=json.loads(row['review_images']) if row['review_images'] else None
        stats=session_map.get(row['id']) if row['source_type']=='word' else None
        if stats:stats['accuracy']=round((stats['correct_count'] or 0)/stats['total_count']*100,1) if stats['total_count'] else 0;stats['review_type']=1
        row['word_review_stats']=stats
    return {'total':total['total'],'items':rows}


async def create_set(request,payload):
    """验证题目后创建练习和关联。"""
    db=Database(request.scope['env'].DB)
    ids=payload.get('question_ids',[])
    if not isinstance(ids,list) or not 1<=len(ids)<=90 or any(type(item) is not int for item in ids) or len(set(ids))!=len(ids):
        raise HTTPException(422,'请选择1至90道不同的题目')
    rows=await db.all('SELECT * FROM question WHERE deleted=0 AND id IN ('+','.join('?' for _ in ids)+')',ids)
    if len(rows)!=len(ids):raise HTTPException(400,'部分题目不存在或已删除')
    if len({row['subject_id'] for row in rows})!=1:raise HTTPException(400,'请选择同一学科的题目')
    similar_ids={}
    if payload.get('question_type')=='similar':
        from similar import generate
        for row in rows:
            existing=await db.first('SELECT id FROM similar_question WHERE source_question_id=? AND deleted=0 ORDER BY id DESC LIMIT 1',(row['id'],))
            if not existing:existing=await generate(row['id'],request)
            similar_ids[row['id']]=existing['id']
    stamp=now().isoformat(' ')
    name=payload.get('name') or '练习集_'+now().strftime('%Y%m%d%H%M%S')
    row=await db.first('INSERT INTO practice_set(name,subject_id,source_type,question_type,total_questions,reviewed,review_count,deleted,created_at) VALUES(?,?,\'question\',?,?,0,0,0,?) RETURNING *',(name,rows[0]['subject_id'],payload.get('question_type','original'),len(ids),stamp))
    await db.batch([('INSERT INTO practice_set_question(practice_set_id,question_id,similar_question_id,display_order) VALUES(?,?,?,?)',(row['id'],question_id,similar_ids.get(question_id),index)) for index,question_id in enumerate(ids)])
    return await get(db,row['id'])


@router.post('',status_code=201)
async def create(request:Request):
    """创建选中错题的练习集。"""
    return await create_set(request,await request.json())


@router.post('/generate-from-questions',status_code=201)
async def generate_questions(request:Request):
    """按未复习、需巩固、其他的优先级抽取题目。"""
    payload=await request.json();db=Database(request.scope['env'].DB)
    count=payload.get('count',5)
    if type(count) is not int or not 1<=count<=90:raise HTTPException(422,'题数需在1至90之间')
    rows=await db.all('SELECT id FROM question WHERE deleted=0 AND subject_id=?'+(' AND grade=?' if payload.get('grade') else '')+' ORDER BY CASE WHEN COALESCE(review_count,0)=0 THEN 0 WHEN error_count>0 OR correct_count*1.0/NULLIF(review_count,0)<0.6 THEN 1 ELSE 2 END,RANDOM() LIMIT ?',[payload.get('subject_id'),*([payload['grade']] if payload.get('grade') else []),count])
    if not rows:raise HTTPException(400,'没有符合条件的题目')
    result=await create_set(request,{'question_ids':[row['id'] for row in rows]})
    from pdf import generate_practice
    try:result.update(await generate_practice(result['id'],request))
    except HTTPException as error:result['pdf_error']=error.detail
    return result


@router.post('/generate-from-reading',status_code=201)
async def generate_reading(request:Request):
    """创建关联现有短文的阅读练习。"""
    payload=await request.json();db=Database(request.scope['env'].DB)
    passage=await db.first('SELECT * FROM reading_passage WHERE id=? AND deleted=0',(payload.get('passage_id'),))
    if not passage:raise HTTPException(404,'短文不存在')
    subject=await db.first('SELECT id FROM subject WHERE name=\'英语\' AND deleted=0')
    if not subject:raise HTTPException(400,'缺少英语学科')
    count=await db.first('SELECT COUNT(*) AS count FROM reading_question WHERE passage_id=? AND deleted=0',(passage['id'],))
    row=await db.first('INSERT INTO practice_set(name,subject_id,source_type,question_type,passage_id,total_questions,reviewed,review_count,deleted,created_at) VALUES(?,?,\'reading\',\'original\',?,?,0,0,0,?) RETURNING id',(payload.get('name') or passage['title'],subject['id'],passage['id'],count['count'],now().isoformat(' ')))
    return await get(db,row['id'])


@router.get('/{practice_set_id}')
async def detail(practice_set_id:int,request:Request):
    """读取练习集详情。"""
    return await get(Database(request.scope['env'].DB),practice_set_id)


@router.put('/{practice_set_id}')
async def update(practice_set_id:int,request:Request):
    """更新名称与备注。"""
    db=Database(request.scope['env'].DB);await get(db,practice_set_id,False)
    payload=await request.json();data={key:value for key,value in payload.items() if key in ('name','notes') and value is not None}
    if data:await db.run('UPDATE practice_set SET '+','.join(key+'=?' for key in data)+' WHERE id=? AND deleted=0',[*data.values(),practice_set_id])
    return {'message':'更新成功'}


@router.put('/{practice_set_id}/review-images')
async def images(practice_set_id:int,request:Request):
    """更新批改原图关联。"""
    db=Database(request.scope['env'].DB);await get(db,practice_set_id,False)
    payload=await request.json();images=payload.get('images')
    if images is not None and not isinstance(images,list):raise HTTPException(422,'图片列表无效')
    await db.run('UPDATE practice_set SET review_images=? WHERE id=? AND deleted=0',(json.dumps(images,ensure_ascii=False),practice_set_id))
    return {'message':'更新成功','review_images':images}


@router.post('/{practice_set_id}/mark-reviewed')
async def reviewed(practice_set_id:int,request:Request):
    """在同一批处理中保存逐题批改、计数与练习正确率。"""
    db=Database(request.scope['env'].DB);practice=await get(db,practice_set_id)
    payload=await request.json() if 'application/json' in request.headers.get('content-type','') else dict(await request.form())
    results=payload.get('question_results') or []
    if isinstance(results,str):results=json.loads(results)
    if not isinstance(results,list):raise HTTPException(422,'批改数据无效')
    mapping={item.get('question_id'):item.get('is_correct') for item in results}
    all_correct=payload.get('is_all_correct') in (True,'true','1')
    stamp=now().isoformat(' ');statements=[];correct=0;plan=[]
    for item in practice['questions']:
        result=True if all_correct else mapping.get(item['question_id'])
        if result is not None and type(result) is not bool:raise HTTPException(422,'批改结果需为布尔值')
        if result:correct+=1
        if practice['source_type']=='question':
            plan.append({'id':item['id'],'question_id':item['question_id'],'graded':int(result is not None),'correct':int(result is True),'error':int(result is False)})
    if plan:
        packed=json.dumps(plan)
        statements.append(('UPDATE question SET review_count=COALESCE(review_count,0)+(SELECT COUNT(*) FROM json_each(?) WHERE json_extract(value,\'$.question_id\')=question.id),correct_count=COALESCE(correct_count,0)+(SELECT SUM(json_extract(value,\'$.correct\')) FROM json_each(?) WHERE json_extract(value,\'$.question_id\')=question.id),error_count=COALESCE(error_count,0)+(SELECT SUM(json_extract(value,\'$.error\')) FROM json_each(?) WHERE json_extract(value,\'$.question_id\')=question.id),last_reviewed_at=? WHERE deleted=0 AND id IN(SELECT json_extract(value,\'$.question_id\') FROM json_each(?))',(packed,packed,packed,stamp,packed)))
        statements.append(('UPDATE practice_set_question SET is_correct=(SELECT json_extract(value,\'$.correct\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=practice_set_question.id) WHERE deleted=0 AND id IN(SELECT json_extract(value,\'$.id\') FROM json_each(?) WHERE json_extract(value,\'$.graded\')=1)',(packed,packed)))
    total=len(results) if practice['source_type']=='reading' else 0 if practice['source_type']=='word' else len(practice['questions'])
    if practice['source_type']=='reading':correct=sum(bool(item.get('is_correct')) for item in results)
    accuracy=round(correct/total*100,1) if total else None
    images=payload.get('images')
    if isinstance(images,list):images=json.dumps(images,ensure_ascii=False)
    statements.append(('UPDATE practice_set SET reviewed=1,review_count=COALESCE(review_count,0)+1,last_reviewed_at=?,accuracy=?,review_images=COALESCE(?,review_images) WHERE id=? AND deleted=0',(stamp,accuracy,images,practice_set_id)))
    await db.batch(statements)
    from motivation import trigger
    try:await trigger(db,'review_practice_set','复习练习集')
    except HTTPException:pass
    return {'message':'已标记为复习','review_count':(practice['review_count'] or 0)+1,'accuracy':accuracy}


async def remove(db,practice_id):
    """软删除练习；按场次明细原子回滚单词复习计数。"""
    practice=await get(db,practice_id,False)
    statements=[('UPDATE write_guard SET revision=CASE WHEN EXISTS(SELECT 1 FROM practice_set WHERE id=? AND deleted=0) THEN revision+1 ELSE NULL END WHERE id=1',(practice_id,))]
    if practice['source_type']=='word':
        plan=[]
        for session in await db.all('SELECT * FROM word_review_session WHERE deleted=0 AND practice_set_id=?',(practice_id,)):
            for item in json.loads(session['word_results'] or '[]'):
                plan.append({'word_id':item.get('word_id'),'correct':int(bool(item.get('is_correct'))),'stamp':session['reviewed_at']})
        if plan:
            packed=json.dumps(plan)
            statements.append(('UPDATE word SET review_count=MAX(0,COALESCE(review_count,0)-(SELECT COUNT(*) FROM json_each(?) WHERE json_extract(value,\'$.word_id\')=word.id)),correct_count=MAX(0,COALESCE(correct_count,0)-(SELECT SUM(json_extract(value,\'$.correct\')) FROM json_each(?) WHERE json_extract(value,\'$.word_id\')=word.id)) WHERE deleted=0 AND id IN(SELECT json_extract(value,\'$.word_id\') FROM json_each(?))',(packed,packed,packed)))
            statements.append(('UPDATE word_review_log SET deleted=1 WHERE id IN(SELECT (SELECT l.id FROM word_review_log l WHERE l.word_id=json_extract(j.value,\'$.word_id\') AND l.is_correct=json_extract(j.value,\'$.correct\') AND l.deleted=0 AND l.reviewed_at>=datetime(json_extract(j.value,\'$.stamp\'),\'-2 minutes\') AND l.reviewed_at<=datetime(json_extract(j.value,\'$.stamp\'),\'+3 hours\') ORDER BY l.reviewed_at DESC,l.id DESC LIMIT 1) FROM json_each(?) j)',(packed,)))
        statements.append(('UPDATE word_review_session SET deleted=1 WHERE practice_set_id=? AND deleted=0',(practice_id,)))
    statements.append(('UPDATE practice_set SET deleted=1 WHERE id=? AND deleted=0',(practice_id,)))
    await db.batch(statements)


@router.delete('/{practice_set_id}',status_code=204)
async def delete(practice_set_id:int,request:Request):
    """软删除单套练习。"""
    await remove(Database(request.scope['env'].DB),practice_set_id)
    from fastapi.responses import Response
    return Response(status_code=204)


@router.post('/batch-delete')
async def batch_delete(request:Request):
    """按现有单套删除语义批量处理。"""
    db=Database(request.scope['env'].DB);payload=await request.json();ids=payload.get('ids',[])
    if not isinstance(ids,list) or not ids:raise HTTPException(422,'请选择练习集')
    deleted=0
    for item in dict.fromkeys(ids):
        try:await remove(db,item);deleted+=1
        except HTTPException as error:
            if error.status_code!=404:raise
    return {'success':True,'deleted_count':deleted,'total':len(ids)}


@router.post('/{practice_set_id}/generate-pdf')
async def pdf(practice_set_id:int,request:Request):
    """按现有打印模板生成 PDF。"""
    from pdf import generate_practice
    return await generate_practice(practice_set_id,request)


@router.post('/batch-download-pdf')
async def batch_pdf(request:Request):
    """返回已生成 PDF 的下载地址。"""
    payload=await request.json();db=Database(request.scope['env'].DB);results=[]
    for item in payload.get('ids',[]):
        row=await db.first('SELECT id,name,pdf_path FROM practice_set WHERE id=? AND deleted=0',(item,))
        results.append({'id':item,'name':row['name'] if row else None,'pdf_url':'/uploads/'+row['pdf_path'] if row and row['pdf_path'] else None,'error':None if row and row['pdf_path'] else 'PDF未生成或练习集不存在'})
    return {'results':results}
