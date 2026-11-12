"""按用户请求生成相似题，批量生成时优先复用已有结果。"""

import html
from fastapi import APIRouter,HTTPException,Request
from database import Database
from analytics import now
from knowledge import question_links
from settings import generate_json
from prompts import PromptLibrary

router=APIRouter(prefix='/api/questions')


async def create_similar(db, request, original: dict, prompt: str) -> dict:
    """调一次模型生成相似题，校验后写入 similar_question（含解析）并返回新行；不触发激励。"""
    # 经模块属性取 generate_json，测试可以替换
    result = await generate_json(request, prompt)
    if not result.get('similar_question') or not result.get('similar_answer'):
        raise HTTPException(502, '生成的题目或答案为空')
    text, answer = html.unescape(result['similar_question']), html.unescape(result['similar_answer'])
    explanation = html.unescape(result.get('explanation') or '')
    if original['subject_name'] == '数学':
        import pdf
        # 数学题一次校验题目、答案、解析里的公式
        await pdf.validate_math(request, [text, answer, explanation])
    return await db.first(
        'INSERT INTO similar_question(source_question_id,similar_text,similar_answer,explanation,similarity_score,'
        'deleted,generated_at) VALUES(?,?,?,?,0.85,0,?) RETURNING *',
        (original['id'], text, answer, explanation, now().isoformat(' ')))


async def reusable_similar(db, question_id: int):
    """最新的一道带解析、没删除、没被任何未删除练习集的未删除题目行引用的相似题；没有则返回 None。"""
    return await db.first(
        'SELECT * FROM similar_question s WHERE s.source_question_id=? AND s.deleted=0 '
        "AND s.explanation IS NOT NULL AND s.explanation<>'' "
        'AND NOT EXISTS(SELECT 1 FROM practice_set_question pq JOIN practice_set p ON p.id=pq.practice_set_id '
        'AND p.deleted=0 WHERE pq.similar_question_id=s.id AND pq.deleted=0) '
        'ORDER BY s.id DESC LIMIT 1', (question_id,))


@router.post('/{question_id}/similar')
async def generate(question_id:int,request:Request):
    """根据原题和知识点生成结构化相似题。"""
    db=Database(request.scope['env'].DB)
    original=await db.first('SELECT q.*,s.name AS subject_name FROM question q JOIN subject s ON s.id=q.subject_id AND s.deleted=0 WHERE q.id=? AND q.deleted=0',(question_id,))
    if not original:raise HTTPException(404,'错题不存在')
    if original['review_status']!='approved':raise HTTPException(409,'这道题还在待核对，处理后才能生成相似题')
    text = original['parsed_question'] or original['original_text']
    if not text:
        raise HTTPException(400, '错题文本为空，无法生成相似题')
    links = (await question_links(db, [question_id])).get(question_id, [])
    row = await create_similar(db, request, original, PromptLibrary()._build_prompt(
        text, original['answer'] or '', original['subject_name'], links))
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
