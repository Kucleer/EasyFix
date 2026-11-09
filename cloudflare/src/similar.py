"""按用户请求生成相似题，批量生成时优先复用已有结果。"""

import html
from fastapi import APIRouter,HTTPException,Request
from database import Database
from analytics import now
from settings import generate_json
from prompts import PromptLibrary

router=APIRouter(prefix='/api/questions')


@router.post('/{question_id}/similar')
async def generate(question_id:int,request:Request):
    """根据原题和知识点生成结构化相似题。"""
    db=Database(request.scope['env'].DB)
    original=await db.first('SELECT q.*,s.name AS subject_name FROM question q JOIN subject s ON s.id=q.subject_id AND s.deleted=0 WHERE q.id=? AND q.deleted=0',(question_id,))
    if not original:raise HTTPException(404,'错题不存在')
    text=original['parsed_question'] or original['original_text']
    if not text:raise HTTPException(400,'错题文本为空，无法生成相似题')
    result=await generate_json(request,PromptLibrary()._build_prompt(text,original['answer'] or '',original['subject_name'],original['knowledge_point'] or ''))
    if not result.get('similar_question') or not result.get('similar_answer'):raise HTTPException(502,'生成的题目或答案为空')
    text,answer=html.unescape(result['similar_question']),html.unescape(result['similar_answer'])
    if original['subject_name']=='数学':
        from pdf import validate_math
        await validate_math(request,[text,answer,result.get('explanation','')])
    row=await db.first('INSERT INTO similar_question(source_question_id,similar_text,similar_answer,similarity_score,deleted,generated_at) VALUES(?,?,?,0.85,0,?) RETURNING *',(question_id,text,answer,now().isoformat(' ')))
    from motivation import trigger
    try:await trigger(db,'generate_similar','生成相似题')
    except HTTPException:pass
    return row


@router.post('/batch-similar')
async def batch(request:Request):
    """批量复用已有相似题，缺少时再调用模型。"""
    payload=await request.json();ids=payload.get('question_ids',[])
    if not isinstance(ids,list) or len(ids)>20:raise HTTPException(422,'每批最多20道题')
    db=Database(request.scope['env'].DB);results=[]
    for question_id in ids:
        try:
            row=await db.first('SELECT id FROM similar_question WHERE source_question_id=? AND deleted=0 ORDER BY id DESC LIMIT 1',(question_id,))
            if not row:row=await generate(question_id,request)
            results.append({'question_id':question_id,'similar_question_id':row['id'],'error':None})
        except HTTPException as error:results.append({'question_id':question_id,'similar_question_id':None,'error':error.detail})
    success=sum(row['error'] is None for row in results)
    return {'success_count':success,'failed_count':len(results)-success,'results':results}
