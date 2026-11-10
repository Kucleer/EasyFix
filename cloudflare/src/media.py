"""原图、奖励图片与音频的按需存储接口。"""

import hashlib
import json
from uuid import uuid4
from urllib.parse import quote
from fastapi import APIRouter,HTTPException,Request,File,UploadFile,Query
from fastapi.responses import Response
from database import Database
from analytics import now
from audio_index import AUDIO_INDEX

router=APIRouter()


async def save_image(request,file):
    """校验并保存图片，统一返回兼容路径字段。"""
    from js import Object
    from pyodide.ffi import to_js
    if file.content_type not in ('image/jpeg','image/jpg','image/png','image/webp'):raise HTTPException(400,'不支持的图片类型')
    content=await file.read(10*1024*1024+1)
    if not content or len(content)>10*1024*1024:raise HTTPException(400,'图片为空或超过10MB')
    name=(file.filename or 'image').replace('/','_').replace('\\','_')
    key=now().strftime('%Y/%m/')+uuid4().hex[:8]+'_'+name
    await request.scope['env'].IMAGES.put(key,to_js(content),to_js({'httpMetadata':{'contentType':file.content_type}},dict_converter=Object.fromEntries))
    return {'path':key,'image_path':key,'original_filename':file.filename,'size':len(content)}


@router.post('/api/upload/batch-simple')
async def batch(request:Request,files:list[UploadFile]=File(...)):
    """保存一批原图，逐项返回失败原因。"""
    if len(files)>10:raise HTTPException(422,'每批最多10张图片')
    items=[]
    for file in files:
        try:items.append({**await save_image(request,file),'success':True})
        except HTTPException as error:items.append({'original_filename':file.filename,'success':False,'error':error.detail})
    success=sum(item['success'] for item in items)
    return {'images':items,'total_count':len(items),'success_count':success,'failed_count':len(items)-success}


@router.post('/api/upload/to-error-book/{error_book_id}')
async def to_book(error_book_id:int,request:Request,files:list[UploadFile]=File(...)):
    """在错题本中保留原图关联。"""
    db=Database(request.scope['env'].DB)
    book=await db.first('SELECT * FROM error_book WHERE id=? AND deleted=0',(error_book_id,))
    if not book:raise HTTPException(404,'错题本不存在')
    result=await batch(request,files)
    items=[item for item in result['images'] if item['success']]
    paths=json.loads(book['original_images'] or '[]')+[item['image_path'] for item in items]
    await db.run('UPDATE error_book SET original_images=?,cover_image=COALESCE(cover_image,?) WHERE id=? AND deleted=0',(json.dumps(paths,ensure_ascii=False),items[0]['image_path'] if items else None,error_book_id))
    return {'error_book_id':error_book_id,'images':items}


@router.post('/api/rewards/{reward_id}/upload-image')
async def reward_image(reward_id:int,request:Request,file:UploadFile=File(...)):
    """上传奖励图片并返回原接口字段。"""
    db=Database(request.scope['env'].DB)
    if not await db.first('SELECT id FROM reward WHERE id=? AND deleted=0',(reward_id,)):raise HTTPException(404,'奖励不存在')
    item=await save_image(request,file);url='/uploads/'+item['path']
    await db.run('UPDATE reward SET image_url=? WHERE id=? AND deleted=0',(url,reward_id))
    return {'Image_url':url,'image_url':url}


@router.get('/api/words/{word_id}/audio')
async def audio(word_id:int,request:Request):
    """优先复用 R2 音频，缺少时才请求现有词典来源。"""
    from js import fetch,Uint8Array,Object,AbortSignal
    from pyodide.ffi import to_js
    db=Database(request.scope['env'].DB)
    word=await db.first('SELECT english FROM word WHERE id=? AND deleted=0',(word_id,))
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


@router.post('/api/words/generate-audio')
async def generate_audio(request:Request,grade:int|None=None):
    """按用户节约调用的要求，音频改为播放时生成并缓存。"""
    row=await Database(request.scope['env'].DB).first('SELECT COUNT(*) AS total FROM word WHERE deleted=0'+(' AND grade=?' if grade else ''),[grade] if grade else [])
    return {'total':row['total'],'message':'音频采用按需缓存：首次播放时生成，之后复用，不批量请求未播放的单词。'}


PRINT_WORD_COLUMNS='id,english,chinese,entry_type,focus_spec,focus_status,focus_updated_at,dictation_level,grade'


async def select_print_words(db,count,grade,word_ids):
    """选取要打印的单词：给定 word_ids 时按传入顺序打印这些未删除的词（忽略 count/grade），否则随机抽样。"""
    if word_ids is not None:
        # 逗号分隔的整数，最多 100 个；非法片段跳过
        ids=[int(part) for part in word_ids.split(',') if part.strip().isdigit()]
        if len(ids)>100:raise HTTPException(422,'每次最多打印100个单词')
        if not ids:return []
        rows=await db.all('SELECT '+PRINT_WORD_COLUMNS+' FROM word WHERE deleted=0 AND id IN ('+','.join('?' for _ in ids)+')',ids)
        by_id={row['id']:row for row in rows}
        # 保持传入顺序，跳过已删除或不存在的 id
        return [by_id[i] for i in ids if i in by_id]
    return await db.all('SELECT '+PRINT_WORD_COLUMNS+' FROM word WHERE deleted=0'+(' AND grade=?' if grade else '')+' ORDER BY RANDOM() LIMIT ?',[*([grade] if grade else []),count])


@router.post('/api/words/print-pdf')
async def print_words(request:Request,count:int=Query(25,ge=1,le=100),grade:int|None=None,dictation_level:int=Query(1,ge=1,le=3),word_ids:str|None=None):
    """生成默写试卷：已标注词组按档位出完形填空；未标注词组仅「提示」档给首字母，其余与单词一样保持「中文 （N个字母）」。给定 word_ids 时只打印这些词。"""
    from phrase_focus import build_cells,default_spec,print_text,split_tokens
    from word_focus import load_focus_context
    db=Database(request.scope['env'].DB)
    words=await select_print_words(db,count,grade,word_ids)
    if not words:raise HTTPException(400,'没有可打印的单词')
    # 一次批量载入全部已标注词组的重点，不按词查询
    context=await load_focus_context(db,words)
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
    key='practice_sets/word_'+uuid4().hex+'.pdf'
    from js import Object
    from pyodide.ffi import to_js
    await request.scope['env'].IMAGES.put(key,await result.js_object.arrayBuffer(),to_js({'httpMetadata':{'contentType':'application/pdf'}},dict_converter=Object.fromEntries))
    return {'pdf_url':'/uploads/'+key}
