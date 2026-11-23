"""单词音频的按需缓存与单词打印接口；图片上传由 Pages 网关直接写入 R2。"""

import hashlib
from uuid import uuid4
from urllib.parse import quote
from fastapi import APIRouter,HTTPException,Request,Query
from fastapi.responses import Response
from database import Database
from audio_index import AUDIO_INDEX
from identity import current_identity, upload_prefix

router=APIRouter()


@router.get('/api/words/{word_id}/audio')
async def audio(word_id:int,request:Request):
    """优先复用 R2 音频，缺少时才请求现有词典来源。"""
    from js import fetch,Uint8Array,Object,AbortSignal
    from pyodide.ffi import to_js
    db=Database(request.scope['env'].DB)
    word=await db.first('SELECT english FROM word WHERE id=? AND student_id=? AND deleted=0',(word_id,current_identity(request)['student_id']))
    if not word:raise HTTPException(404,'单词不存在')
    english=word['english'];bucket=request.scope['env'].IMAGES
    key='audio/words/'+hashlib.sha256(english.lower().encode()).hexdigest()+'.mp3'
    cached=await bucket.get(AUDIO_INDEX.get(english.lower(),key))
    if cached is None:
        for extension in ('.mp3','.wav'):
            cached=await bucket.get('audio/words/'+english.lower()+extension)
            if cached is not None:break
    if cached is not None:
        content=Uint8Array.new(await cached.arrayBuffer()).to_py().tobytes()
        content_type=getattr(cached.httpMetadata,'contentType',None) or 'audio/mpeg'
        return Response(content,media_type=content_type,headers={'Cache-Control':'private, max-age=86400'})
    from auth import maintenance_enabled
    if await maintenance_enabled(request):
        # 维护期间只允许命中缓存；回源会写 R2，属于副作用。
        raise HTTPException(503,'系统维护中，请稍后再试')
    urls=['https://dict.youdao.com/dictvoice?type=1&audio='+quote(english)]
    for url in urls:
        options=to_js({'headers':{'User-Agent':'EasyFix/1.0'}},dict_converter=Object.fromEntries);options.signal=AbortSignal.timeout(15000)
        result=await fetch(url,options)
        content_type=result.headers.get('content-type') or ''
        if result.status==200 and content_type.startswith('audio'):
            data=await result.arrayBuffer()
            if data.byteLength>500:
                await bucket.put(key,data,to_js({'httpMetadata':{'contentType':content_type}},dict_converter=Object.fromEntries))
                return Response(Uint8Array.new(data).to_py().tobytes(),media_type=content_type,headers={'Cache-Control':'private, max-age=86400'})
    raise HTTPException(502,'音频来源暂时不可用，请稍后重试')


PRINT_WORD_COLUMNS='id,english,chinese,entry_type,focus_spec,focus_status,focus_updated_at,dictation_level,grade'


async def select_print_words(db,student_id,count,grade,word_ids):
    """选取要打印的单词：给定 word_ids 时按传入顺序打印这些未删除的词（忽略 count/grade），否则随机抽样。"""
    if word_ids is not None:
        # 逗号分隔的整数，最多 100 个；非法片段跳过
        ids=[int(part) for part in word_ids.split(',') if part.strip().isdigit()]
        if len(ids)>100:raise HTTPException(422,'每次最多打印100个单词')
        if not ids:return []
        rows=await db.all('SELECT '+PRINT_WORD_COLUMNS+' FROM word WHERE deleted=0 AND student_id=? AND id IN ('+','.join('?' for _ in ids)+')',[student_id,*ids])
        by_id={row['id']:row for row in rows}
        # 保持传入顺序，跳过已删除或不存在的 id
        return [by_id[i] for i in ids if i in by_id]
    return await db.all('SELECT '+PRINT_WORD_COLUMNS+' FROM word WHERE deleted=0 AND student_id=?'+(' AND grade=?' if grade else '')+' ORDER BY RANDOM() LIMIT ?',[student_id,*([grade] if grade else []),count])


@router.post('/api/words/print-pdf')
async def print_words(request:Request,count:int=Query(25,ge=1,le=100),grade:int|None=None,dictation_level:int=Query(1,ge=1,le=3),word_ids:str|None=None):
    """生成默写试卷：已标注词组按档位出完形填空；未标注词组仅「提示」档给首字母，其余与单词一样保持「中文 （N个字母）」。给定 word_ids 时只打印这些词。"""
    from phrase_focus import build_cells,default_spec,print_text,split_tokens
    from word_focus import load_focus_context
    db=Database(request.scope['env'].DB)
    owner=current_identity(request)
    words=await select_print_words(db,owner['student_id'],count,grade,word_ids)
    if not words:raise HTTPException(400,'没有可打印的单词')
    # 一次批量载入全部已标注词组的重点，不按词查询
    context=await load_focus_context(db,owner['student_id'],words)
    questions=[]
    for word in words:
        item=context.get(word['id'])
        tokens=None
        if item:
            tokens,_=build_cells(item['spec'],word['dictation_level'],dictation_level,item['focus'])
        elif dictation_level==2 and word['entry_type']=='phrase' and len(split_tokens(word['english']))>1:
            # 未标注词组选「提示」档：不依赖重点，每个词给首字母
            tokens,_=build_cells(default_spec(word['english']),3,2,[])
        questions.append({'question_text':print_text(word,tokens)})
    from pdf import call
    result=await call(request,'/pdf',{'title':'单词默写','questions':questions})
    # 新 PDF 放在本家庭的前缀下，网关按前缀判断归属
    key=upload_prefix(owner['user_id'])+'practice_sets/word_'+uuid4().hex+'.pdf'
    from js import Object
    from pyodide.ffi import to_js
    await request.scope['env'].IMAGES.put(key,await result.js_object.arrayBuffer(),to_js({'httpMetadata':{'contentType':'application/pdf'}},dict_converter=Object.fromEntries))
    return {'pdf_url':'/uploads/'+key}
