// 将授权与日志保存在被忽略的本机目录，不依赖临时 npx 目录的随机名称。
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..');
const candidates=[path.join(root,'cloudflare/node_modules/wrangler')];
const cache=path.join(root,'tmp/npm-cache/_npx');
if(fs.existsSync(cache))for(const entry of fs.readdirSync(cache))candidates.push(path.join(cache,entry,'node_modules/wrangler'));
const installation=candidates.find(directory=>{
  try{return JSON.parse(fs.readFileSync(path.join(directory,'package.json'),'utf8')).version==='4.158.0';}catch{return false;}
});
if(!installation){console.error('Run npm install --prefix cloudflare first.');process.exit(1);}
const config=path.join(root,'tmp/cloudflare-config');
const result=spawnSync(process.execPath,[...process.execArgv,path.join(installation,'bin/wrangler.js'),...process.argv.slice(2)],{stdio:'inherit',env:{...process.env,XDG_CONFIG_HOME:config,WRANGLER_LOG_PATH:path.join(config,'logs'),WRANGLER_SEND_METRICS:'false'}});
process.exit(result.status??1);
