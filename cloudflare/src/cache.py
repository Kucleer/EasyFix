"""短时复用统计结果，通过数据库版本号使跨实例缓存失效。"""

import time
from database import Database

ENTRIES={}
PATHS={'/api/stats/summary','/api/stats/today','/api/stats/overview','/api/stats/knowledge-points','/api/stats/analysis/full','/api/starmap'}


async def lookup(request):
    """缓存命中时只读取一次版本，避免重复执行全部统计 SQL。"""
    if request.method!='GET' or request.url.path not in PATHS:return None,None
    db=Database(request.scope['env'].DB)
    row=await db.first('SELECT value FROM runtime_config WHERE name=\'data_revision\' AND deleted=0')
    revision=row['value'] if row else '0'
    key=(str(request.url),revision)
    entry=ENTRIES.get(key)
    if entry and entry[0]>time.monotonic():return entry[1],key
    return None,key


def remember(key,body,media_type):
    """限制缓存大小，不存储登录或模型密钥配置。"""
    if key is None or len(body)>256*1024:return
    if len(ENTRIES)>=64:ENTRIES.clear()
    ENTRIES[key]=(time.monotonic()+60,(body,media_type))


async def invalidate(request):
    """业务写入后递增共享版本，所有实例的旧统计随之失效。"""
    ENTRIES.clear()
    import json
    from datetime import datetime,timedelta
    parts=request.url.path.strip('/').split('/')
    resource=parts[1] if len(parts)>1 else 'app'
    target_id=next((int(part) for part in parts[2:] if part.isdigit()),None)
    operation={('POST','questions'):'create_question',('PUT','questions'):'update_question',('DELETE','questions'):'delete_question',('POST','error-books'):'create_error_book',('PUT','error-books'):'update_error_book'}.get((request.method,resource),request.method.lower()+'_'+resource)
    if resource=='upload':operation='upload'
    if resource=='config':operation='config'
    if 'similar' in request.url.path:operation='generate_similar'
    await Database(request.scope['env'].DB).batch([
      ('UPDATE runtime_config SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE name=\'data_revision\' AND deleted=0',()),
      ('INSERT INTO operation_log(operator,operation_type,operation_status,target_type,target_id,request_data,deleted,created_at) VALUES(\'cloudflare\',?,\'success\',?,?,?,0,?)',(operation,resource,target_id,json.dumps({'method':request.method,'path':request.url.path}),(datetime.utcnow()+timedelta(hours=8)).isoformat(' ')))])
