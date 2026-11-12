"""使用内部渲染服务生成 PDF 并保存到私有 R2。"""

import json
from uuid import uuid4
from fastapi import HTTPException
from database import Database


async def call(request,path,payload):
    """通过服务绑定调用渲染器，无需公网请求或账号 API 凭证。"""
    response=await request.scope['env'].PDF.fetch('https://pdf.internal'+path,method='POST',headers={'Content-Type':'application/json'},body=json.dumps(payload,ensure_ascii=False))
    if response.status>=400:
        try:detail=json.loads(await response.text()).get('detail','PDF生成失败')
        except ValueError:detail='PDF生成失败'
        raise HTTPException(response.status,detail)
    return response


async def validate_math(request,texts):
    """正式写入数学题前，使用相同 KaTeX 版本校验公式。"""
    await call(request,'/validate',{'texts':texts})


TEMPLATE_VERSION='2'
TARGETED_TEMPLATE_VERSION='4'  # 4：留白放大 1.5 倍（2026-11-12）
# 入选原因的中文名，和前端考点卷页面一致
REASON_LABELS={'new':'新错题','wrong':'上次做错','redo':'旧错题重做','consolidate':'巩固','check':'验收','spot':'抽查'}
FORM_LABELS={'original':'原题','similar':'相似题'}
DIGITS='零一二三四五六七八九'


def chinese_number(number):
    """把 1~99 写成中文数字（组标题的序号）：1→一，10→十，12→十二，20→二十。"""
    if number<10:return DIGITS[number]
    tens,ones=divmod(number,10)
    return ('' if tens==1 else DIGITS[tens])+'十'+(DIGITS[ones] if ones else '')


def primary_link(item):
    """取这道题的主考点；没有主考点取排在最前的一个，都没有返回 None。"""
    links=sorted(item.get('knowledge_points') or [],
                 key=lambda point:(0 if point.get('is_primary') else 1,point.get('id') or 0))
    return links[0] if links else None


def picked_link(item):
    """出卷时这道题是为哪个考点选的：按 knowledge_point_id 在关联里找；列为空或找不到时退回主考点。"""
    picked=item.get('knowledge_point_id')
    if picked is not None:
        for point in item.get('knowledge_points') or []:
            if point.get('id')==picked:return point
    return primary_link(item)


def space_size(item):
    """作答留白档位：有选项 's'；否则按答案字数，不超过 20 字 's'、不超过 80 字 'm'，更长 'l'。"""
    if any(item.get('option_'+letter) for letter in 'abcd'):return 's'
    length=len(str(item.get('answer') or ''))
    return 's' if length<=20 else 'm' if length<=80 else 'l'


def build_targeted_payload(practice):
    """考点卷的版式内容：按一级模块分组（组内保持题号顺序），另附家长用的答案页。"""
    groups,order=[],{}
    answers=[]
    for item in sorted(practice['questions'],key=lambda row:row.get('number') or 0):
        link=picked_link(item)
        module=(link.get('parent_name') or link.get('name')) if link else '其他'
        # 按一级模块的编号分组（和手机、出卷页一致），两个同名模块不会并成一组；组标题仍用模块名
        module_key=(link.get('parent_id') or link.get('id')) if link else None
        if module_key not in order:
            order[module_key]=len(groups)
            groups.append({'module':module,'questions':[]})
        question={'number':item['number'],'question_text':item['question_text']}
        for letter in 'abcd':question['option_'+letter]=item.get('option_'+letter)
        question['space']=space_size(item)
        groups[order[module_key]]['questions'].append(question)
        point=' / '.join(part for part in (link.get('parent_name'),link.get('name')) if part) if link else ''
        similar=item.get('form')=='similar'
        answers.append({'number':item['number'],'answer':item.get('answer'),
                        'analysis':item.get('explanation') if similar else item.get('analysis'),
                        'point':point,'form':FORM_LABELS['similar' if similar else 'original'],
                        'reason':REASON_LABELS.get(item.get('reason'),'')})
    code='#'+str(practice['id'])
    return {'template_version':TARGETED_TEMPLATE_VERSION,'layout':'targeted','title':practice['name'],'code':code,
            'groups':[{'title':'%s、%s（%d 题）'%(chinese_number(index),group['module'],len(group['questions'])),
                       'questions':group['questions']} for index,group in enumerate(groups,1)],
            'answers':answers,
            'footer':'手机上从首页的"专项练习"进待批改，找到 '+code}


def build_payload(practice):
    """把练习详情变成渲染器的输入。考点卷走新版式；其余和过去逐字段相同，旧 PDF 的指纹不变。"""
    if practice.get('kind')=='targeted':return build_targeted_payload(practice)
    printable=[]
    for item in practice['questions']:
        links=sorted(item.get('knowledge_points') or [],
                     key=lambda point:(0 if point.get('is_primary') else 1,point.get('id') or 0))
        primary=next((point for point in links if point.get('is_primary')),None)
        path='/'.join(part for part in (primary.get('parent_name'),primary.get('name')) if part) if primary else None
        fields={key:item.get(key) for key in ('question_text','difficulty','error_type','option_a','option_b','option_c','option_d','is_reading_question','topic')}
        fields['id']=item.get('question_id',item['id'])
        fields['knowledge_path']=[{'id':point.get('id'),'parent_id':point.get('parent_id'),
                                   'parent_name':point.get('parent_name'),'name':point.get('name'),
                                   'is_primary':bool(point.get('is_primary'))} for point in links]
        fields['knowledge_point']=(path+'（主考点）') if path else None
        printable.append(fields)
    return {'template_version':TEMPLATE_VERSION,'title':practice['name'],'questions':printable,'passage':practice.get('passage')}


async def ensure_printable(db,practice):
    """考点卷还有"题面是相似题、但还没配相似题"的题时不能打印（409）；只多查一条 SQL，别的卷子不查。

    这种题如果直接打印，卷面会印出原题却标成相似题、答案页也没有解析，所以要先在出卷页准备完。
    """
    if practice.get('kind')!='targeted':return
    # 和出卷页 prepare 数"还没准备"的条件相同：错题已删除的行不在卷面上，不算
    row=await db.first("SELECT COUNT(*) AS count FROM practice_set_question pq JOIN question q ON q.id=pq.question_id "
                       "AND q.deleted=0 WHERE pq.practice_set_id=? AND pq.deleted=0 AND pq.form='similar' "
                       "AND pq.similar_question_id IS NULL",(practice['id'],))
    if row and row['count']:
        raise HTTPException(409,'还有 %d 道相似题没准备好，请先在出卷页准备完'%row['count'])


async def generate_practice(practice_set_id,request):
    """读取真实练习内容，渲染成功后才更新 PDF 路径。"""
    from practices import get
    db=Database(request.scope['env'].DB)
    practice=await get(db,practice_set_id)
    if not practice['questions']:raise HTTPException(400,'练习集没有题目')
    await ensure_printable(db,practice)
    import hashlib
    payload=build_payload(practice)
    fingerprint=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    cache_name='pdf:'+str(practice_set_id)
    cached=await db.first('SELECT value FROM runtime_config WHERE name=? AND deleted=0',(cache_name,))
    if cached and cached['value']==fingerprint and practice.get('pdf_path'):
        return {'pdf_url':'/uploads/'+practice['pdf_path']}
    response=await call(request,'/pdf',payload)
    key='practice_sets/'+uuid4().hex+'.pdf'
    from js import Object
    from pyodide.ffi import to_js
    await request.scope['env'].IMAGES.put(key,await response.js_object.arrayBuffer(),to_js({'httpMetadata':{'contentType':'application/pdf'}},dict_converter=Object.fromEntries))
    await db.run('UPDATE practice_set SET pdf_path=? WHERE id=? AND deleted=0',(key,practice_set_id))
    await db.run('INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES(?,?,0,CURRENT_TIMESTAMP) ON CONFLICT(name) DO UPDATE SET value=excluded.value,deleted=0,updated_at=excluded.updated_at',(cache_name,fingerprint))
    return {'pdf_url':'/uploads/'+key}
