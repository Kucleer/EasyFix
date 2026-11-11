"""云端运行配置持久化与文本模型请求。"""

import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from database import Database

router = APIRouter(prefix='/api/config')


async def load(request, name, default=None):
    """读取 D1 配置，缺省时使用部署的初始化配置。"""
    row = await Database(request.scope['env'].DB).first('SELECT value FROM runtime_config WHERE name=? AND deleted=0', (name,))
    if row:
        return json.loads(row['value'])
    if name == 'llm':
        return json.loads(str(getattr(request.scope['env'], 'LLM_CONFIG', '{}')))
    if name == 'app':
        return json.loads(str(getattr(request.scope['env'], 'APP_CONFIG', '{}')))
    return default or {}


async def store(request, name, value):
    """使用参数化语句保存运行配置。"""
    await Database(request.scope['env'].DB).run('INSERT INTO runtime_config(name,value,deleted,updated_at) VALUES (?,?,0,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value,deleted=0,updated_at=excluded.updated_at', (name, json.dumps(value, ensure_ascii=False), datetime.utcnow().isoformat()))


@router.get('/app')
async def app_config(request: Request):
    """读取默认年级与学期。"""
    return {'default_grade': None, 'default_semester': None, **await load(request, 'app')}


@router.post('/app')
async def save_app(request: Request):
    """保存学段设置，不推断未提供的值。"""
    payload = await request.json()
    data = {key: payload.get(key) for key in ('default_grade', 'default_semester')}
    for key, high in [('default_grade', 12), ('default_semester', 2)]:
        if data[key] is not None and (type(data[key]) is not int or not 1 <= data[key] <= high):
            raise HTTPException(422, '默认年级或学期无效')
    await store(request, 'app', data)
    return {'message': '应用配置已保存', 'data': data}


@router.get('/llm')
async def llm_config(request: Request):
    """返回脱敏配置，前端无需获取服务端完整 API 密钥。"""
    config = await load(request, 'llm')
    if config.get('api_key'):
        config['api_key'] = '********'
    return config


@router.post('/llm')
async def save_llm(request: Request):
    """保存模型配置，掩码代表沿用已有密钥。"""
    old = await load(request, 'llm')
    data = await request.json()
    if not isinstance(data, dict) or not isinstance(data.get('base_url'), str) or not data['base_url'].startswith('https://'):
        raise HTTPException(422, '模型地址需要使用 HTTPS')
    config = {key: data.get(key, old.get(key, '')) for key in ('provider', 'api_key', 'base_url', 'model')}
    if config['api_key'] == '********':
        config['api_key'] = old.get('api_key', '')
    await store(request, 'llm', config)
    return {'message': 'LLM配置已保存'}


DEFAULT_MAX_TOKENS = 6000
DEFAULT_TEMPERATURE = 0.6


async def generate_json(request, prompt, max_tokens=DEFAULT_MAX_TOKENS, temperature=DEFAULT_TEMPERATURE):
    """通过云端异步 HTTP 调用现有文本模型，解析结构化 JSON。

    max_tokens、temperature 可选：不传时和原来完全一样（相似题、学习报告不受影响）。
    Anthropic 接口原来不传随机度，所以只有调用方给了不同于默认的值时才传。
    """
    from js import fetch,Object,AbortSignal
    from pyodide.ffi import to_js
    config = await load(request, 'llm')
    if not config.get('api_key') or not config.get('base_url'):
        raise HTTPException(503, '请先配置文本模型')
    anthropic = config.get('provider')=='anthropic' or '/anthropic' in config['base_url']
    base=config['base_url'].rstrip('/')
    url = base + ('/messages' if base.endswith('/v1') else '/v1/messages') if anthropic else base + '/chat/completions'
    system='你是严谨的学习辅导助手。仅返回有效JSON。数学公式使用带边界的LaTeX，保留反斜杠。'
    body={'model':config.get('model'),'max_tokens':max_tokens,'messages':[{'role':'user','content':prompt}]}
    headers={'x-api-key':config['api_key'],'anthropic-version':'2023-06-01'} if anthropic else {'Authorization':'Bearer '+config['api_key']}
    headers['Content-Type']='application/json'
    if anthropic:
        body['system']=system;body['thinking']={'type':'disabled'}
        if temperature!=DEFAULT_TEMPERATURE:body['temperature']=temperature
    else:body['messages'].insert(0,{'role':'system','content':system});body['temperature']=temperature
    options=to_js({'method':'POST','headers':headers,'body':json.dumps(body,ensure_ascii=False)},dict_converter=Object.fromEntries)
    options.signal=AbortSignal.timeout(120000)
    response=await fetch(url,options)
    if response.status >= 400:
        raise HTTPException(502, '文本模型请求失败，请检查模型配置和余额')
    try:
        result=json.loads(await response.text())
        content = ''.join(block.get('text','') for block in result.get('content',[]) if block.get('type')=='text').strip() if anthropic else result['choices'][0]['message']['content'].strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0]
        return json.loads(content)
    except (KeyError, IndexError, ValueError):
        raise HTTPException(502, '模型没有返回有效的结构化内容')
