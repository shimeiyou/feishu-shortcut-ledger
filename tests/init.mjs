import assert from 'node:assert/strict';
import {schema,initialize,request} from '../tools/init-bitable.mjs';
const spec=schema();assert.equal(spec.table.fields.length,6);assert.equal(spec.formulas.length,3);
assert.equal(spec.table.fields.find(f=>f.field_name==='分类').type,3);
assert(spec.formulas[1].property.formula_expression.includes('[来源]="自动联动"'));
let calls=[];
const env={FEISHU_APP_ID:'cli_example',FEISHU_APP_SECRET:'synthetic-only',FEISHU_APP_TOKEN:'ExampleBase'};
const mock=async(url,options)=>{
  calls.push({url,options});let json;
  if(url.includes('/auth/'))json={code:0,tenant_access_token:'fixture'};
  else if(options.method==='GET')json={code:0,data:{items:[],has_more:false}};
  else if(url.endsWith('/tables'))json={code:0,data:{table_id:'tblExample'}};
  else json={code:0,data:{}};
  return {ok:true,status:200,json:async()=>json};
};
const result=await initialize(env,false,mock);assert.equal(result.tableId,'tblExample');
assert.equal(calls.filter(c=>c.options.method==='POST').length,5);
assert(!calls.some(c=>c.url.includes('records'))); // no samples without opt-in
calls=[];
await assert.rejects(initialize(env,false,async(url,opts)=>{
  if(url.includes('/auth/'))return mock(url,opts);
  return {ok:true,status:200,json:async()=>({code:0,data:{items:[{name:'一体账本'}],has_more:false}})};
}));
assert.equal(calls.length,1); // only auth; existing tables were never modified
await assert.rejects(request('/test','POST',null,{},async()=>({ok:true,status:200,json:async()=>({})})));
console.log('Initializer schema, creation, no-sample default, existing-table protection and strict response checks passed.');
