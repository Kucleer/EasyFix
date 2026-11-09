import puppeteer from '@cloudflare/puppeteer';
import katex from 'katex';
import katexScript from './assets/katex.txt';
import autoRenderScript from './assets/auto-render.txt';
import mathScript from './assets/math-text.txt';
import style from './assets/katex-css.txt';

const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const origin = 'https://easyfix-bl2.pages.dev';

function validate(texts) {
  for (const raw of texts) {
    const text = String(raw ?? '');
    if (/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(text)) throw new Error('公式包含异常控制字符');
    let consumed = text;
    const pattern = /\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]|\$\$([\s\S]*?)\$\$/g;
    consumed = consumed.replace(pattern, (_,inline,display,dollar) => {
      katex.renderToString(inline ?? display ?? dollar, {displayMode:inline===undefined,trust:false,throwOnError:true,maxExpand:200,maxSize:20});
      return '';
    });
    if (/\\\(|\\\)|\\\[|\\\]|\$\$/.test(consumed)) throw new Error('公式边界不匹配');
  }
}

export default {
  async fetch(request,env) {
    if (request.method!=='POST') return new Response('Method not allowed',{status:405});
    const payload=await request.json();
    if (new URL(request.url).pathname==='/validate') {
      try {validate(payload.texts || []);return Response.json({valid:true});}
      catch(error){return Response.json({detail:String(error.message).slice(0,400)},{status:422});}
    }
    if (!Array.isArray(payload.questions) || payload.questions.length>100) return Response.json({detail:'打印题目数量无效'},{status:422});
    let browser;
    try {
      browser=await puppeteer.launch(env.BROWSER);
      const page=await browser.newPage();
      await page.setViewport({width:673,height:978});
      await page.setRequestInterception(true);
      page.on('request',req=>{
        const url=req.url();
        if (url.startsWith(origin+'/assets/math/v0.19.0/fonts/') || url.startsWith('data:') || url==='about:blank') req.continue();
        else req.abort();
      });
      const texts=[];
      const field=(value,label)=>{const index=texts.length;texts.push({text:String(value??''),label});return `<div class="math-field" data-field="${index}"></div>`;};
      let blocks='';
      if (payload.passage) blocks+=`<section class="passage">${field(payload.passage.title,'短文标题')}${field(payload.passage.content,'短文')}</section>`;
      for (const [index,q] of payload.questions.entries()) {
        if (!String(q.question_text || '').trim()) throw new Error(`题目${q.id??index+1}缺少题干`);
        let content=field(q.question_text,`题目${q.id??index+1}`);
        for(const letter of ['a','b','c','d']) if(q['option_'+letter]) content+=field(letter.toUpperCase()+'. '+String(q['option_'+letter]).replace(/^(?:[A-Da-d]\s*[.、．)]|\([A-Da-d]\))\s*/,''),'选项'+letter.toUpperCase());
        if(q.include_solution) content+=field(q.answer,'答案')+field(q.analysis,'解析');
        blocks+=`<section class="question"><div class="question-header">第 ${index+1} 题${q.id?'　|　ID: '+escape(q.id):''}${q.knowledge_point?'　|　知识点：'+escape(q.knowledge_point):''}</div>${content}<div class="answer-space"></div></section>`;
      }
      const documentHtml=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><base href="${origin}/assets/math/v0.19.0/"><style>${style}\n@page{size:A4;margin:18mm 16mm 20mm}*{box-sizing:border-box}body{margin:0;color:#111;font-family:"Noto Sans CJK SC","Noto Sans SC",sans-serif;font-size:11pt;line-height:1.9}h1{text-align:center;font-size:18pt}.question{border-top:1px solid #888;padding-top:3mm;margin-bottom:10mm;break-inside:avoid}.question.long{break-inside:auto}.question-header{font-size:9pt;color:#333}.math-field{white-space:pre-wrap;overflow-wrap:anywhere}.katex{white-space:nowrap}.katex-display{margin:3mm 0;break-inside:avoid}.answer-space{height:12mm}.passage{margin-bottom:8mm}</style></head><body><h1>${escape(payload.title)}</h1>${blocks}</body></html>`;
      await page.setContent(documentHtml,{waitUntil:'load'});
      await page.addScriptTag({content:katexScript});
      await page.addScriptTag({content:autoRenderScript});
      await page.addScriptTag({content:mathScript,type:'module'});
      await page.waitForFunction('Boolean(window.EasyFixMath)');
      const errors=await page.evaluate(items=>items.flatMap((item,index)=>window.EasyFixMath.renderMathText(document.querySelector(`[data-field="${index}"]`),item.text,renderMathInElement).map(error=>item.label+'：'+error)),texts);
      if(errors.length)return Response.json({detail:errors.slice(0,5).join('；')},{status:422});
      await page.evaluate(async()=>{await document.fonts.ready;document.querySelectorAll('.question').forEach(el=>{if(el.getBoundingClientRect().height>900)el.classList.add('long');});});
      const tooWide=await page.evaluate(()=>[...document.querySelectorAll('.katex')].some(el=>el.getBoundingClientRect().width>el.closest('.math-field').clientWidth+1));
      if(tooWide)return Response.json({detail:'公式过宽，请拆成多行'},{status:422});
      await page.emulateMediaType('print');
      const bytes=await page.pdf({format:'A4',preferCSSPageSize:true,printBackground:true,displayHeaderFooter:true,headerTemplate:'<span></span>',footerTemplate:'<div style="font-size:9px;width:100%;text-align:center">第 <span class="pageNumber"></span> / <span class="totalPages"></span> 页</div>'});
      return new Response(bytes,{headers:{'Content-Type':'application/pdf'}});
    } catch(error) {
      const message=String(error.message);
      return Response.json({detail:message.slice(0,400)},{status:503});
    } finally {if(browser)await browser.close();}
  }
};
