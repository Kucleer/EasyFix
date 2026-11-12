"""练习集创建、批改和软删除，保留题目关联与单词复习明细。"""

import json
import random
from fastapi import APIRouter,HTTPException,Query,Request
from database import Database
from analytics import now
from question_scope import COUNTED
from knowledge import (ensure_guard_rows,guard_statement,link_statements,
                       question_links,resolve_many,structure_statement)
from knowledge_model import map_error, projection_name
import starmap
from targeted_model import question_state

router=APIRouter(prefix='/api/practice-sets')


async def batch_or_http(db, statements):
    """执行 D1 batch，并把触发器错误映射为明确的 409/422/503。"""
    try:
        return await db.batch(statements)
    except Exception as error:
        mapped = map_error(error)
        if mapped:
            raise HTTPException(mapped[0], mapped[1])
        raise


async def word_stats(db,practice_id):
    """聚合单词练习的原始场次信息。"""
    row=await db.first('SELECT SUM(total_count) AS total_count,SUM(correct_count) AS correct_count,SUM(duration) AS duration,MAX(reviewed_at) AS reviewed_at FROM word_review_session WHERE deleted=0 AND practice_set_id=?',(practice_id,))
    if not row or not row['total_count']: return None
    row['accuracy']=round((row['correct_count'] or 0)/row['total_count']*100,1)
    log=await db.first('SELECT review_type FROM word_review_log WHERE reviewed_at=? AND deleted=0 ORDER BY id DESC LIMIT 1',(row['reviewed_at'],))
    row['review_type']=log['review_type'] if log else 1
    return row


async def word_practice_items(db,practice_id):
    """返回单词练习的逐词明细：含逐词结果、默写档位，以及截至本场次的累计错误次数。"""
    logs=await db.all('SELECT l.*,w.english,w.chinese,w.phonetic FROM word_review_session s JOIN word_review_log l ON l.reviewed_at=s.reviewed_at AND l.deleted=0 JOIN word w ON w.id=l.word_id AND w.deleted=0 WHERE s.deleted=0 AND s.practice_set_id=? ORDER BY l.id',(practice_id,))
    # 一次批量查询每条日志对应单词截至该日志（含）的累计错误次数，避免逐词查询（Workers 免费版限制）
    pairs=[{'log_id':item['id'],'word_id':item['word_id']} for item in logs]
    error_counts={}
    if pairs:
        rows=await db.all('SELECT json_extract(j.value,\'$.log_id\') AS log_id,'
                          '(SELECT COUNT(*) FROM word_review_log l WHERE l.deleted=0 AND l.is_correct=0 '
                          'AND l.word_id=json_extract(j.value,\'$.word_id\') '
                          'AND l.id<=json_extract(j.value,\'$.log_id\')) AS error_count '
                          'FROM json_each(?) j',(json.dumps(pairs),))
        error_counts={row['log_id']:row['error_count'] for row in rows}
    items=[]
    for index,item in enumerate(logs):
        items.append({'id':item['id'],'question_id':item['word_id'],'display_order':index,
                      'question_text':item['english'],'answer':item['chinese'],'phonetic':item['phonetic'],
                      'is_correct':bool(item['is_correct']),'user_answer':item['user_answer'],
                      # 逐词结果解析为列表或 null；默写档位直接取日志列
                      'token_results':json.loads(item['token_results']) if item['token_results'] else None,
                      'dictation_level':item['dictation_level'],
                      # 累计错误次数：同一单词 is_correct=0 且 id 不晚于本条日志的记录数
                      'error_count':error_counts.get(item['id'],0),
                      'knowledge_point':None,'knowledge_points':[],'tags':[]})
    return items


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
                row['questions'].append({'id':item['id'],'question_id':item['id'],'display_order':item['question_number']-1,'question_text':item['question_text'],'answer':item['correct_answer'],'original_question_text':item['question_text'],'original_answer':item['correct_answer'],'difficulty':passage['difficulty'],'topic':passage['topic'],'knowledge_point':None,'knowledge_points':[],'legacy_knowledge_point':None,'is_correct':None,'is_reading_question':True,'tags':[],**{key:item[key] for key in ('option_a','option_b','option_c','option_d','explanation')}})
    elif row['source_type']=='word':
        row['questions']=await word_practice_items(db,practice_id)
    else:
        rows=await db.all('SELECT pq.*,q.subject_id,q.parsed_question,q.original_text,q.answer,q.difficulty,q.knowledge_point,q.legacy_knowledge_point,q.knowledge_revision,q.error_type,q.review_count,q.original_image,q.analysis,s.similar_text,s.similar_answer,s.explanation FROM practice_set_question pq JOIN question q ON q.id=pq.question_id AND q.deleted=0 LEFT JOIN similar_question s ON s.id=pq.similar_question_id AND s.deleted=0 WHERE pq.deleted=0 AND pq.practice_set_id=? ORDER BY pq.display_order',(practice_id,))
        link_map=await question_links(db,[item['question_id'] for item in rows])
        for number,item in enumerate(rows,1):
            original=item['parsed_question'] or item['original_text'] or ''
            item['original_question_text']=original
            item['original_answer']=item['answer']
            # 卷面题号，从 1 开始。考点卷按出卷时写下的顺序（display_order 是 0..n-1）：
            # 卷子印出来以后某道错题被删除，其余题的题号也不变，和纸上对得上；旧练习集仍按剩下的题连续编号
            item['number']=(item['display_order'] or 0)+1 if row.get('kind')=='targeted' else number
            # 题面取相似题：这一行挂了相似题，并且这一行标的是相似题；
            # 旧数据的行没有 form，按整份卷子的 question_type 判断
            use_similar=bool(item['similar_question_id']) and item['similar_text'] is not None and (
                item['form']=='similar' or (item['form'] is None and row['question_type']=='similar'))
            item['question_text']=item['similar_text'] if use_similar else original
            if use_similar:item['answer']=item['similar_answer']
            # 卷面上实际印的是原题还是相似题（批改页显示"原题 / 相似题"标记用）
            item['shown_form']='similar' if use_similar else 'original'
            item['is_correct']=bool(item['is_correct']) if item['is_correct'] is not None else None
            links=link_map.get(item['question_id'],[])
            item['knowledge_points']=links
            item['knowledge_point']=projection_name(links)
            item['knowledge_revision']=item.get('knowledge_revision') or 0
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
    if any(row['review_status']!='approved' for row in rows):raise HTTPException(400,'所选题目里有待核对的题，请先处理')
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
    await batch_or_http(db, [('INSERT INTO practice_set_question(practice_set_id,question_id,similar_question_id,display_order) VALUES(?,?,?,?)',(row['id'],question_id,similar_ids.get(question_id),index)) for index,question_id in enumerate(ids)])
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
    rows=await db.all('SELECT id FROM question WHERE '+COUNTED+' AND subject_id=?'+(' AND grade=?' if payload.get('grade') else '')+' ORDER BY CASE WHEN COALESCE(review_count,0)=0 THEN 0 WHEN error_count>0 OR correct_count*1.0/NULLIF(review_count,0)<0.6 THEN 1 ELSE 2 END,RANDOM() LIMIT ?',[payload.get('subject_id'),*([payload['grade']] if payload.get('grade') else []),count])
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


async def knowledge_review_statements(db,practice,payload,stamp):
    """构造批改时编辑知识点的写入语句，返回 (语句, 实际改动的题目 ID)。"""
    edits=payload.get('question_knowledge') or []
    if isinstance(edits,str):
        try:edits=json.loads(edits)
        except ValueError:raise HTTPException(422,'知识点批改数据无效')
    if not edits:return [], []
    if practice['source_type']!='question':raise HTTPException(422,'只有错题练习可以修改知识点')
    if not isinstance(edits,list):raise HTTPException(422,'知识点批改数据无效')
    valid={}
    for item in edits:
        if not isinstance(item,dict) or type(item.get('question_id')) is not int:raise HTTPException(422,'知识点批改数据无效')
        valid[item['question_id']]=item
    practice_ids={item['question_id'] for item in practice['questions']}
    if set(valid)-practice_ids:raise HTTPException(422,'知识点批改包含不属于本次练习的题目')
    old_map=await question_links(db,sorted(valid))
    entries=[({'knowledge_point_ids':item.get('knowledge_point_ids'),
               'primary_knowledge_point_id':item.get('primary_knowledge_point_id')},
              None,old_map.get(question_id,[]),False) for question_id,item in valid.items()]
    resolved=await resolve_many(db,practice['subject_id'],entries)
    statements=[];changed=[]
    for (question_id,item),(result,detail) in zip(valid.items(),resolved):
        if detail:raise HTTPException(422,detail)
        if not result['changed']:continue
        expected=item.get('knowledge_revision')
        if expected is None:raise HTTPException(409,'分类已变更，请刷新批改数据后重试')
        if type(expected) is not int:raise HTTPException(422,'knowledge_revision 参数无效')
        statements.append(guard_statement(
            'EXISTS(SELECT 1 FROM write_guard WHERE id=1 AND deleted=0) AND '
            'COALESCE((SELECT knowledge_revision FROM question WHERE id=? AND deleted=0),-1)=?',
            (question_id,expected)))
        changed.append((question_id,result))
    if changed:await ensure_guard_rows(db)
    for question_id,result in changed:
        statements+=link_statements(question_id,result['ids'],result['primary'],'manual',stamp)
        name=result['points'][result['primary']]['name'] if result['primary'] else None
        statements.append(('UPDATE question SET knowledge_revision=knowledge_revision+1,knowledge_point=?,updated_at=? WHERE id=? AND deleted=0',(name,stamp,question_id)))
    if changed:statements.append(structure_statement([item[0] for item in changed]))
    return statements,[item[0] for item in changed]


SKIP_REASONS=('not_done','bad_question')   # 跳过原因：没做、题目有误（这道题不计入）
STALE_TEXT='这份卷子刚被批改过，请刷新后再改'


async def changed_knowledge(db,changed_ids):
    """批改时改过知识点的题：返回它们最新的版本号和知识点，供前端刷新。"""
    question_knowledge=[]
    if changed_ids:
        link_map=await question_links(db,changed_ids)
        revisions={row['id']:row['knowledge_revision'] for row in await db.all('SELECT id,knowledge_revision FROM question WHERE id IN ('+','.join('?' for _ in changed_ids)+')',changed_ids)}
        for question_id in changed_ids:
            links=link_map.get(question_id,[])
            question_knowledge.append({'question_id':question_id,'knowledge_revision':revisions.get(question_id,0),'knowledge_points':links,'knowledge_point':projection_name(links)})
    return question_knowledge


async def reward_review(db):
    """触发"复习练习集"的激励；行为没配置时忽略。"""
    from motivation import trigger
    try:await trigger(db,'review_practice_set','复习练习集')
    except HTTPException:pass


def read_revision(payload):
    """读取请求里的 grading_revision：不传返回 None；表单提交时可以是数字字符串；其它格式 422。"""
    value=payload.get('grading_revision')
    if value is None or value=='':return None
    if isinstance(value,str) and value.isdigit():return int(value)
    if type(value) is not int:raise HTTPException(422,'grading_revision 必须是整数')
    return value


def parse_results(practice,results):
    """校验错题练习的逐题结果，返回 {错题编号: (做对 True/False/None, 跳过原因或 None)}。

    每条必须是对象、错题编号属于这份卷子且不重复、is_correct 是布尔值或空、skip_reason 取值正确；
    有跳过原因时这道题按"没批改"存（is_correct 为空）。
    """
    owned={item['question_id'] for item in practice['questions']}
    given={}
    for item in results:
        if not isinstance(item,dict):raise HTTPException(422,'批改数据无效')
        question_id=item.get('question_id')
        if type(question_id) is not int or question_id not in owned:raise HTTPException(422,'批改结果包含不属于本次练习的题目')
        if question_id in given:raise HTTPException(422,'批改结果里有重复的题目')
        correct,skip=item.get('is_correct'),item.get('skip_reason')
        if skip is not None and skip not in SKIP_REASONS:raise HTTPException(422,'跳过原因只能是 %s' % '、'.join(SKIP_REASONS))
        if correct is not None and type(correct) is not bool:raise HTTPException(422,'批改结果需为布尔值')
        given[question_id]=(None,skip) if skip else (correct,None)
    return given


def grading_entries(questions,given,all_correct,first):
    """算出每道题的旧结果和新结果。

    新结果：全对时都算对；提到的题按提交的；没提到的题第一次批改算没批改，之后保持原结果。
    """
    entries=[]
    for item in questions:
        old=(item['is_correct'],item.get('skip_reason'))
        if all_correct:new=(True,None)
        elif item['question_id'] in given:new=given[item['question_id']]
        elif first:new=(None,None)
        else:new=old
        entries.append({'id':item['id'],'question_id':item['question_id'],'number':item['number'],
                        'order':item.get('display_order') or 0,'old':old[0],'new':new[0],'skip':new[1]})
    return entries


def count_deltas(entries,first):
    """按差值算错题计数的加减：review_count 看"批改过没有"的变化，correct/error 看各自的变化。

    touch 表示这次要写错题的 last_reviewed_at（只在第一次批改、并且这道题有对错结果时）。
    没有任何变化的题不写。
    """
    deltas=[]
    for entry in entries:
        old,new=entry['old'],entry['new']
        delta={'question_id':entry['question_id'],
               'review':int(new is not None)-int(old is not None),
               'correct':int(new is True)-int(old is True),
               'error':int(new is False)-int(old is False),
               'touch':int(first and new is not None)}
        if delta['review'] or delta['correct'] or delta['error'] or delta['touch']:
            deltas.append(delta)
    return deltas


async def load_history(db,practice_id):
    """取这份卷子里每道错题的录入时间、主考点，以及它在其它卷子里的有效结果（一条 SQL）。

    没有其它结果的题也返回一行（结果列为空）；所在卷子已删除的结果 set_id 为空，由调用方丢掉。
    """
    return await db.all(
        'SELECT q.id AS question_id,q.created_at AS entered,qk.knowledge_point_id AS point_id,'
        'o.is_correct,o.display_order,ps.id AS set_id,ps.last_reviewed_at '
        'FROM question q '
        'LEFT JOIN question_knowledge_point qk ON qk.question_id=q.id AND qk.deleted=0 AND qk.is_primary=1 '
        'LEFT JOIN practice_set_question o ON o.question_id=q.id AND o.deleted=0 AND o.practice_set_id<>? '
        'AND o.is_correct IS NOT NULL AND o.skip_reason IS NULL '
        'LEFT JOIN practice_set ps ON ps.id=o.practice_set_id AND ps.deleted=0 '
        'WHERE q.deleted=0 AND q.id IN (SELECT question_id FROM practice_set_question WHERE practice_set_id=? AND deleted=0)',
        (practice_id,practice_id))


def graduated_numbers(history,entries,before_at,after_at,waive_map):
    """这次批改后刚好毕业（连对达到 GRADUATE_STREAK）的题，返回卷面题号列表。

    before_at / after_at 是这份卷子批改前后的批改时间；waive_map 是 {考点: 直接设为掌握的时间}。
    """
    from targeted import normal_time
    others,info={},{}
    for row in history:
        info.setdefault(row['question_id'],row)
        if row['set_id'] is not None:
            others.setdefault(row['question_id'],[]).append(
                {'at':normal_time(row['last_reviewed_at']),'order':row['display_order'] or 0,'correct':bool(row['is_correct'])})
    numbers=[]
    for entry in entries:
        row=info.get(entry['question_id'])
        if row is None:continue
        base=others.get(entry['question_id'],[])
        waive_at=waive_map.get(row['point_id'])
        entered=normal_time(row['entered'])

        def state_with(result,at):
            """把这份卷子的结果并进去后算这道题的状态。"""
            extra=[] if result is None else [{'at':normal_time(at),'order':entry['order'],'correct':result}]
            return question_state(base+extra,entered,waive_at)['state']
        if state_with(entry['new'],after_at)=='graduated' and state_with(entry['old'],before_at)!='graduated':
            numbers.append(entry['number'])
    return numbers


async def leaf_nodes(db,request,subject_id,default_grade):
    """算一科二级考点的掌握度：{考点: 节点}；学科不存在时返回空字典（不挡批改）。"""
    try:
        _,nodes,_,_,_=await starmap.compute(db,request,subject_id,default_grade)
    except HTTPException as error:
        if error.status_code!=404:raise
        return {}
    return {node['id']:node for node in nodes if node['level']==2}


def point_changes(before,after):
    """批改前后状态或掌握度有变化的二级考点，以及这次新点亮的考点数。"""
    def brief(node):
        """只留掌握度（保留 4 位小数）和状态。"""
        value=node['value']
        return {'value':round(value,4) if value is not None else None,'status':node['status']}
    points,newly=[],0
    for point_id,node in after.items():
        old=before.get(point_id)
        if old is None:continue
        if brief(old)!=brief(node):
            points.append({'id':point_id,'name':node['name'],'before':brief(old),'after':brief(node)})
        if node['status']=='mastered' and old['status']!='mastered':newly+=1
    return points,newly


async def review_questions(db,request,practice,payload,results):
    """错题练习的批改（设计 9.2）：按差值计数、版本号防止两人同时修改、支持"没做""题目有误"。

    全部校验在写入之前完成；出错时库里没有任何变化。SQL 条数固定，不随题目数增加。
    """
    practice_id=practice['id']
    given=parse_results(practice,results)
    expected=read_revision(payload)
    current=practice.get('grading_revision') or 0
    if expected is not None and expected!=current:raise HTTPException(409,STALE_TEXT)
    all_correct=payload.get('is_all_correct') in (True,'true','1')
    first=not practice['reviewed']
    stamp=now().isoformat(' ')
    knowledge_statements,changed_ids=await knowledge_review_statements(db,practice,payload,stamp)
    entries=grading_entries(practice['questions'],given,all_correct,first)
    graded=[entry for entry in entries if entry['new'] is not None]
    # 正确率 = 做对的题数 ÷ 有对错结果的题数（"没做""题目有误"不算在分母里）
    accuracy=round(sum(1 for entry in graded if entry['new'])/len(graded)*100,1) if graded else None
    images=payload.get('images')
    if isinstance(images,list):images=json.dumps(images,ensure_ascii=False)

    # 批改前：默认年级只读一次；掌握度和各题的历史结果各取一次
    default_grade=await starmap.load_default_grade(request)
    before_nodes=await leaf_nodes(db,request,practice['subject_id'],default_grade)
    history=await load_history(db,practice_id)
    await ensure_guard_rows(db)

    # 第一条是事务内断言：版本号还是读到的那个，否则整批回滚（两人同时提交时后到的失败，计数不会重复）
    statements=[guard_statement('COALESCE((SELECT grading_revision FROM practice_set WHERE id=? AND deleted=0),-1)=?',(practice_id,current))]
    statements+=knowledge_statements
    deltas=count_deltas(entries,first)
    if deltas:
        packed=json.dumps(deltas)
        pick='(SELECT SUM(json_extract(value,\'$.%s\')) FROM json_each(?) WHERE json_extract(value,\'$.question_id\')=question.id)'
        statements.append((
            'UPDATE question SET review_count=MAX(0,COALESCE(review_count,0)+'+pick % 'review'+'),'
            'correct_count=MAX(0,COALESCE(correct_count,0)+'+pick % 'correct'+'),'
            'error_count=MAX(0,COALESCE(error_count,0)+'+pick % 'error'+'),'
            'last_reviewed_at=CASE WHEN '+pick % 'touch'+'>0 THEN ? ELSE last_reviewed_at END '
            'WHERE deleted=0 AND id IN(SELECT json_extract(value,\'$.question_id\') FROM json_each(?))',
            (packed,packed,packed,packed,stamp,packed)))
    if entries:
        rows=json.dumps([{'id':entry['id'],'correct':None if entry['new'] is None else int(entry['new']),'skip':entry['skip']} for entry in entries])
        statements.append((
            'UPDATE practice_set_question SET '
            'is_correct=(SELECT json_extract(value,\'$.correct\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=practice_set_question.id),'
            'skip_reason=(SELECT json_extract(value,\'$.skip\') FROM json_each(?) WHERE json_extract(value,\'$.id\')=practice_set_question.id) '
            'WHERE deleted=0 AND id IN(SELECT json_extract(value,\'$.id\') FROM json_each(?))',(rows,rows,rows)))
    if first:
        statements.append(('UPDATE practice_set SET reviewed=1,review_count=COALESCE(review_count,0)+1,last_reviewed_at=?,accuracy=?,review_images=COALESCE(?,review_images),grading_revision=COALESCE(grading_revision,0)+1 WHERE id=? AND deleted=0',(stamp,accuracy,images,practice_id)))
    else:
        # 之后的修改不动批改次数和批改时间，这次练习在时间线上的位置不变
        statements.append(('UPDATE practice_set SET accuracy=?,review_images=COALESCE(?,review_images),grading_revision=COALESCE(grading_revision,0)+1 WHERE id=? AND deleted=0',(accuracy,images,practice_id)))
    try:
        await batch_or_http(db,statements)
    except HTTPException as error:
        # 没有知识点编辑时，409 只可能来自版本号断言
        if error.status_code==409 and not knowledge_statements:raise HTTPException(409,STALE_TEXT)
        raise

    # 批改后：再算一次掌握度，找出变化的考点和刚毕业的题
    after_nodes=await leaf_nodes(db,request,practice['subject_id'],default_grade)
    from targeted import normal_time
    waive_map={point_id:normal_time(node.get('waive_at')) for point_id,node in after_nodes.items()}
    after_at=stamp if first else practice['last_reviewed_at']
    graduated=graduated_numbers(history,entries,practice['last_reviewed_at'],after_at,waive_map)
    points,newly_mastered=point_changes(before_nodes,after_nodes)
    question_knowledge=await changed_knowledge(db,changed_ids)
    if first:await reward_review(db)       # 激励只在第一次批改时发
    return {'message':'已标记为复习','review_count':(practice['review_count'] or 0)+(1 if first else 0),
            'accuracy':accuracy,'question_knowledge':question_knowledge,'grading_revision':current+1,
            'points':points,'newly_mastered':newly_mastered,'graduated':graduated}


@router.post('/{practice_set_id}/mark-reviewed')
async def reviewed(practice_set_id:int,request:Request):
    """保存一份练习的批改：错题练习按差值计数（review_questions），阅读、单词练习照旧（review_other）。"""
    db=Database(request.scope['env'].DB);practice=await get(db,practice_set_id)
    payload=await request.json() if 'application/json' in request.headers.get('content-type','') else dict(await request.form())
    results=payload.get('question_results') or []
    if isinstance(results,str):
        try:results=json.loads(results)
        except ValueError:raise HTTPException(422,'批改数据无效')
    if not isinstance(results,list):raise HTTPException(422,'批改数据无效')
    if practice['source_type'] in ('reading','word'):
        return await review_other(db,practice,payload,results)
    # 其余都是错题练习（和 get 的判断一致）
    return await review_questions(db,request,practice,payload,results)


async def review_other(db,practice,payload,results):
    """阅读、单词练习的批改：保持原来的做法（每提交一次批改次数加一）。"""
    practice_set_id=practice['id']
    mapping={item.get('question_id'):item.get('is_correct') for item in results}
    all_correct=payload.get('is_all_correct') in (True,'true','1')
    stamp=now().isoformat(' ')
    knowledge_statements,changed_ids=await knowledge_review_statements(db,practice,payload,stamp)
    statements=list(knowledge_statements);correct=0
    for item in practice['questions']:
        result=True if all_correct else mapping.get(item['question_id'])
        if result is not None and type(result) is not bool:raise HTTPException(422,'批改结果需为布尔值')
        if result:correct+=1
    total=len(results) if practice['source_type']=='reading' else 0 if practice['source_type']=='word' else len(practice['questions'])
    if practice['source_type']=='reading':correct=sum(bool(item.get('is_correct')) for item in results)
    accuracy=round(correct/total*100,1) if total else None
    images=payload.get('images')
    if isinstance(images,list):images=json.dumps(images,ensure_ascii=False)
    statements.append(('UPDATE practice_set SET reviewed=1,review_count=COALESCE(review_count,0)+1,last_reviewed_at=?,accuracy=?,review_images=COALESCE(?,review_images) WHERE id=? AND deleted=0',(stamp,accuracy,images,practice_set_id)))
    await batch_or_http(db, statements)
    question_knowledge=await changed_knowledge(db,changed_ids)
    await reward_review(db)
    return {'message':'已标记为复习','review_count':(practice['review_count'] or 0)+1,'accuracy':accuracy,'question_knowledge':question_knowledge}


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
    await batch_or_http(db, statements)


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
