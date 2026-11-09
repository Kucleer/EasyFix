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


async def generate_practice(practice_set_id,request):
    """读取真实练习内容，渲染成功后才更新 PDF 路径。"""
    from practices import get
    db=Database(request.scope['env'].DB)
    practice=await get(db,practice_set_id)
    if not practice['questions']:raise HTTPException(400,'练习集没有题目')
    import hashlib
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
    payload={'template_version':TEMPLATE_VERSION,'title':practice['name'],'questions':printable,'passage':practice.get('passage')}
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
