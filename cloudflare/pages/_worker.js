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

export default{
  async fetch(request,env){
    try{
      const url=new URL(request.url);
      if(url.pathname.startsWith('/assets/')){
        const original=await env.ASSETS.fetch(request);const response=new Response(original.body,original);
        response.headers.set('Cache-Control','public, max-age=31536000, immutable');return response;
      }
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
