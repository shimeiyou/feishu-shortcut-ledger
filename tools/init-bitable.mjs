#!/usr/bin/env node
/** Create a NEW unified table only. Preview is default; --apply opts in. */
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
const ROOT=new URL('../',import.meta.url);
export function schema(config=JSON.parse(fs.readFileSync(new URL('config/shortcut-config.example.json',ROOT),'utf8'))) {
  const categories=[...new Set(config.branches.flatMap(b=>b.categories.map(c=>c.name)).concat('生意结余'))];
  return {table:{name:'一体账本',default_view_name:'收支明细',fields:[
    {field_name:'事件',type:1},
    {field_name:'时间',type:5,property:{date_formatter:'yyyy/MM/dd HH:mm',auto_fill:true}},
    {field_name:'收支',type:2,property:{formatter:'0.00'}},
    {field_name:'账本',type:3,property:{options:[{name:'生意'},{name:'生活'}]}},
    {field_name:'分类',type:3,property:{options:categories.map(name=>({name}))}},
    {field_name:'来源',type:1}
  ]},formulas:[
    {field_name:'月份',type:20,property:{formula_expression:'TEXT([时间],"YYYY/MM")'}},
    {field_name:'收入',type:20,property:{formula_expression:'IF(AND([账本]="生活",[分类]="生意结余",[来源]="自动联动"),[收支],IF([收支]>0,[收支],0))',formatter:'0.00'}},
    {field_name:'支出',type:20,property:{formula_expression:'IF(AND([账本]="生活",[分类]="生意结余",[来源]="自动联动"),0,IF([收支]<0,ABS([收支]),0))',formatter:'0.00'}}
  ]};
}
export async function request(path,method='GET',token,body,fetcher=fetch) {
  const res=await fetcher('https://open.feishu.cn/open-apis'+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const data=await res.json();
  if(!res.ok||data.code!==0) throw Error('飞书接口失败：HTTP '+res.status+'，code='+data.code+'；请检查权限，勿盲目重复提交。');
  return data;
}
export async function initialize(env,insertSample=false,fetcher=fetch) {
  const {FEISHU_APP_ID:app_id,FEISHU_APP_SECRET:app_secret,FEISHU_APP_TOKEN:appToken}=env;
  if(!/^cli_[A-Za-z0-9]+$/.test(app_id||'')||!app_secret||!/^[A-Za-z0-9]+$/.test(appToken||''))throw Error('请设置 FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_APP_TOKEN');
  const req=(p,m,t,b)=>request(p,m,t,b,fetcher);
  const auth=await req('/auth/v3/tenant_access_token/internal','POST',null,{app_id,app_secret});
  const token=auth.tenant_access_token;if(!token)throw Error('缺少授权令牌');
  const prefix='/bitable/v1/apps/'+appToken+'/tables', spec=schema();
  let cursor=null;const seen=new Set();
  do {
    const {data}=await req(prefix+'?page_size=100'+(cursor?'&page_token='+encodeURIComponent(cursor):''),'GET',token);
    if(!Array.isArray(data?.items))throw Error('数据表列表响应异常');
    if(data.items.some(t=>t.name===spec.table.name))throw Error('已存在“一体账本”，为保护原表，本脚本不再建表或修改它。请核对已有结构。');
    if(!data.has_more)break;
    cursor=data.page_token;if(!cursor||seen.has(cursor))throw Error('数据表列表分页异常');seen.add(cursor);
  }while(true);
  const {data}=await req(prefix,'POST',token,{table:spec.table});
  const id=data?.table_id;if(!id)throw Error('建表结果不确定，请先去飞书核对，勿重复执行');
  console.log('已创建新表 FEISHU_TABLE_ID='+id+'；后续失败时先检查此表，不要重复建表。');
  for(const field of spec.formulas)await req(prefix+'/'+id+'/fields','POST',token,field);
  if(insertSample){
    const samples=JSON.parse(fs.readFileSync(new URL('config/sample-records.json',ROOT),'utf8'));
    await req(prefix+'/'+id+'/records/batch_create','POST',token,{records:samples.map(fields=>({fields}))});
  }
  return {tableId:id,recordUrl:'https://open.feishu.cn/open-apis'+prefix+'/'+id+'/records'};
}
async function main(){
  const args=process.argv.slice(2);
  if(args.some(a=>!['--apply','--dry-run','--insert-sample','--help'].includes(a)))throw Error('未知参数；使用 --help 查看用法');
  if(args.includes('--help')){console.log('node tools/init-bitable.mjs [--dry-run | --apply] [--insert-sample]\n默认预览，不联网。--apply 只新建一张表，不修改旧表。凭证使用环境变量。');return;}
  if(!args.includes('--apply')||args.includes('--dry-run')){console.log(JSON.stringify(schema(),null,2));return;}
  console.log(JSON.stringify(await initialize(process.env,args.includes('--insert-sample')),null,2));
}
if(process.argv[1]===fileURLToPath(import.meta.url))main().catch(e=>{console.error(e.message);process.exitCode=1;});
