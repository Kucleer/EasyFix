let sessionKey;
let sessionKeySource;
const encoder=new TextEncoder();

function constantEqual(left,right){
  if(left.length!==right.length)return false;
  let diff=0;for(let i=0;i<left.length;i++)diff|=left.charCodeAt(i)^right.charCodeAt(i);
  return diff===0;
}

async function authenticated(request,env){
  if(env.ACCESS_TOKEN && constantEqual(request.headers.get('Authorization')||'','Bearer '+env.ACCESS_TOKEN))return true;
  const cookie=(request.headers.get('Cookie')||'').split(';').map(x=>x.trim()).find(x=>x.startsWith('easyfix_session='));
  if(!cookie||!env.SESSION_SECRET)return false;
  const [expires,signature]=cookie.slice('easyfix_session='.length).split('.');
  if(!/^[0-9]+$/.test(expires)||!/^[0-9a-f]{64}$/.test(signature||'')||Number(expires)<=Date.now()/1000)return false;
  if(sessionKeySource!==env.SESSION_SECRET){sessionKey=await crypto.subtle.importKey('raw',encoder.encode(env.SESSION_SECRET),{name:'HMAC',hash:'SHA-256'},false,['verify']);sessionKeySource=env.SESSION_SECRET;}
  return crypto.subtle.verify('HMAC',sessionKey,Uint8Array.from(signature.match(/../g),x=>parseInt(x,16)),encoder.encode(expires));
}

// ---------- 图片上传：在网关直接写入 R2，不经过 Python 后端 ----------
// 为什么放在这里：Python 后端解析一张约 200KB 的照片要用掉约 0.8 秒 CPU，
// 而 Workers 免费计划每个请求只有 10 毫秒；连续传几张后平台会中止后端
// （日志里是 exceededCpu），用户看到的就是 502。
// 网关是 JavaScript，解析表单和写 R2 都由平台原生完成，只花几毫秒。
const UPLOAD_PATHS=['/api/upload/batch-simple','/api/upload/file'];
const IMAGE_TYPES=['image/jpeg','image/jpg','image/png','image/webp'];
const MAX_IMAGE_BYTES=10*1024*1024;
const MAX_BATCH_IMAGES=10;

// 返回 JSON 响应；和后端一样禁止缓存。
function jsonResponse(data,status=200){
  return Response.json(data,{status,headers:{'Cache-Control':'private, no-store'}});
}

// 取北京时间（数据库里的时间都是北京时间）；用 toISOString 读出来就是北京的年月日时分秒。
function beijingNow(){
  return new Date(Date.now()+8*3600*1000);
}

// 读取 D1 里的维护写开关；读不出来按维护中处理，避免默认放行写入（与后端 maintenance_enabled 一致）。
async function maintenanceEnabled(env){
  try{
    const row=await env.DB.prepare("SELECT value FROM runtime_config WHERE name='write_maintenance' AND deleted=0").first();
    if(!row)return false;
    return ['1','true','on','yes'].includes(String(row.value).trim().toLowerCase());
  }catch(error){
    return true;
  }
}

// 校验并保存一张图片。成功返回 {path, original_filename, size}，不合格返回 {error: 中文原因}。
async function saveImage(env,file){
  if(!IMAGE_TYPES.includes(file.type))return {error:'不支持的图片类型'};
  if(file.size===0||file.size>MAX_IMAGE_BYTES)return {error:'图片为空或超过10MB'};
  // 存储路径与后端一致：年/月/8位随机字符_原文件名（文件名里的斜杠换成下划线）
  const name=(file.name||'image').replace(/[\/\\]/g,'_');
  const month=beijingNow().toISOString().slice(0,7).replace('-','/');
  const key=month+'/'+crypto.randomUUID().replace(/-/g,'').slice(0,8)+'_'+name;
  await env.IMAGES.put(key,await file.arrayBuffer(),{httpMetadata:{contentType:file.type}});
  return {path:key,original_filename:file.name,size:file.size};
}

// 记一条操作日志，格式与后端写入成功后记的一致；日志写不进去不影响已经存好的图片。
async function logUpload(env,path){
  try{
    const created=beijingNow().toISOString().replace('T',' ').replace('Z','');
    await env.DB.prepare("INSERT INTO operation_log(operator,operation_type,operation_status,target_type,target_id,request_data,deleted,created_at) VALUES('cloudflare',?,'success',?,NULL,?,0,?)")
      .bind('upload','upload',JSON.stringify({method:'POST',path}),created).run();
  }catch(error){}
}

// 处理图片上传：先做和后端相同的登录、维护开关、来源检查，再逐张保存。
async function handleUpload(request,env,url){
  if(!await authenticated(request,env))return jsonResponse({detail:'需要登录'},401);
  if(await maintenanceEnabled(env))return jsonResponse({detail:'系统维护中，请稍后再试'},503);
  const origin=request.headers.get('Origin');
  if(origin&&origin!==url.origin)return jsonResponse({detail:'请求来源无效'},403);
  let form;
  try{form=await request.formData();}
  catch(error){return jsonResponse({detail:'请求格式不对，需要用表单上传图片'},422);}
  const single=url.pathname==='/api/upload/file';
  // 单张接口的表单字段叫 file，批量接口叫 files；只要文件，忽略普通文本字段
  const files=form.getAll(single?'file':'files').filter(item=>typeof item!=='string');
  if(files.length===0)return jsonResponse({detail:'请选择要上传的图片'},422);
  if(single){
    const saved=await saveImage(env,files[0]);
    if(saved.error)return jsonResponse({detail:saved.error},400);
    await logUpload(env,url.pathname);
    return jsonResponse(saved);
  }
  if(files.length>MAX_BATCH_IMAGES)return jsonResponse({detail:'每批最多10张图片'},422);
  const images=[];
  for(const file of files){
    const saved=await saveImage(env,file);
    if(saved.error)images.push({original_filename:file.name,success:false,error:saved.error});
    else images.push({path:saved.path,image_path:saved.path,original_filename:saved.original_filename,size:saved.size,success:true});
  }
  const success=images.filter(item=>item.success).length;
  await logUpload(env,url.pathname);
  return jsonResponse({images,total_count:images.length,success_count:success,failed_count:images.length-success});
}

export default{
  async fetch(request,env){
    try{
      const url=new URL(request.url);
      if(url.pathname.startsWith('/assets/')){
        const original=await env.ASSETS.fetch(request);const response=new Response(original.body,original);
        response.headers.set('Cache-Control','public, max-age=31536000, immutable');return response;
      }
      if(request.method==='POST'&&UPLOAD_PATHS.includes(url.pathname))return await handleUpload(request,env,url);
      if(url.pathname.startsWith('/api/')||['/login','/health'].includes(url.pathname))return await env.BACKEND.fetch(request);
      const valid=await authenticated(request,env);
      if(url.pathname.startsWith('/uploads/')){
        if(!valid)return Response.json({detail:'需要登录'},{status:401});
        if(!['GET','HEAD'].includes(request.method))return new Response('Method not allowed',{status:405});
        const key=decodeURIComponent(url.pathname.slice('/uploads/'.length));
        if(!key||key.includes('\\')||key.split('/').some(part=>['','.','..'].includes(part)))return Response.json({detail:'附件路径无效'},{status:400});
        const object=await env.IMAGES.get(key,{range:request.headers});
        if(!object)return Response.json({detail:'附件不存在'},{status:404});
        const headers=new Headers();object.writeHttpMetadata(headers);
        if(!/^(image\/(jpeg|jpg|png|webp)|audio\/(mpeg|wav|x-wav)|application\/pdf)$/.test(headers.get('Content-Type')||''))headers.set('Content-Type','application/octet-stream');
        headers.set('ETag',object.httpEtag);headers.set('Cache-Control','private, max-age=86400');headers.set('X-Content-Type-Options','nosniff');headers.set('Accept-Ranges','bytes');
        if(request.headers.get('If-None-Match')===object.httpEtag){await object.body.cancel();return new Response(null,{status:304,headers});}
        let status=200;
        if(request.headers.has('Range')&&object.range){status=206;headers.set('Content-Range',`bytes ${object.range.offset}-${object.range.offset+object.range.length-1}/${object.size}`);headers.set('Content-Length',String(object.range.length));}
        else headers.set('Content-Length',String(object.size));
        if(request.method==='HEAD'){await object.body.cancel();return new Response(null,{status,headers});}
        return new Response(object.body,{status,headers});
      }
      if(!valid)return Response.redirect(new URL('/login',url),303);
      const result=await env.ASSETS.fetch(request);
      if(result.status!==404)return result;
      return env.ASSETS.fetch(new Request(new URL('/index.html',url),request));
    }catch(error){return Response.json({detail:'云端请求失败，请稍后重试'},{status:502,headers:{'Cache-Control':'no-store'}});}
  }
};
