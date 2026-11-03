const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const path=require('path');const root=path.resolve(__dirname,'..');
const core=fs.readFileSync(path.join(root,'apps-script/Code.gs'),'utf8');
const source=core+'\n'+fs.readFileSync(path.join(root,'apps-script/optional-sheets/SheetsBackup.gs'),'utf8');
const store=new Map();const props={getProperty:k=>store.get(k)||null,setProperty(k,v){store.set(k,v);},setProperties(v){Object.entries(v).forEach(([k,v])=>store.set(k,v));},deleteProperty:k=>store.delete(k)};
let tableMap=new Map(),batchCalls=0,forceFailure=false;
function sheet(name){const obj={name,id:tableMap.size+1,data:[],getSheetId(){return this.id},getLastRow(){return this.data.length},getMaxRows(){return 1000},getMaxColumns(){return 26},getRange(row,col,n,w){return {getValues:()=>Array.from({length:n},(_,i)=>Array.from({length:w},(_,j)=>this.data[row+i-1]?.[col+j-1]??''))}}};tableMap.set(name,obj);return obj;}
const ss={getSheetByName:n=>tableMap.get(n),insertSheet:sheet,getId:()=> 'offline-sheet'};
const ctx={console,Date,Set,JSON,Number,Error,PropertiesService:{getScriptProperties:()=>props},
 Utilities:{DigestAlgorithm:{SHA_256:1},Charset:{UTF_8:1},computeDigest:(_,s)=>[...crypto.createHash('sha256').update(s).digest()],formatDate:(date,tz,format)=>{const x=new Date(date.getTime()+8*3600*1000).toISOString();return format==='yyyy/MM'?x.slice(0,7).replace('-','/'):x.slice(0,19).replaceAll('-','/').replace('T',' ');}},
 SpreadsheetApp:{openById:()=>ss,flush(){}},Sheets:{Spreadsheets:{batchUpdate({requests}){batchCalls++;if(forceFailure)throw Error('offline simulated batch failure');for(const req of requests){const q=req.updateCells;if(!q)continue;const target=[...tableMap.values()].find(s=>s.id===q.range.sheetId);target.data=q.rows.map(r=>r.values.map(c=>c.userEnteredValue?.numberValue??c.userEnteredValue?.stringValue??''));}}}}};
vm.createContext(ctx);vm.runInContext(source,ctx);let checks=0;
function check(name,fn){fn();checks++;console.log('ok',name)}
function r(id,amount,book='生意',cat='其他',source='快捷指令',event='测试事件'){return {record_id:id,fields:{'收支':amount,'账本':book,'分类':cat,'来源':source,'事件':event,'时间':Date.parse('2026-10-31T12:00:00+08:00'),'月份':[{'text':'2026/10'}]}}}
let rows=[r('a','100.10'),r('b','20.20'),r('c','-0.30'),r('auto','100.10','生活','生意结余','自动联动','2026/10 生意净结余（自动联动）')];
check('exact cents',()=>{assert.equal(ctx.ledgerCents_('0.01'),1);assert.equal(ctx.ledgerCents_('-0.30'),-30);assert.equal(ctx.ledgerCents_('0'),0)});
check('invalid precision/finite/boolean',()=>{for(const v of ['1.234','NaN','Infinity',null,true,'900719925474099.99'])assert.throws(()=>ctx.ledgerCents_(v))});
check('expected derived difference only',()=>{const before=JSON.stringify(rows),p=ctx.ledgerPlan_(rows);assert.equal(p.length,1);assert.equal(p[0].after,12000);assert.equal(p[0].before,10010);assert.equal(before,JSON.stringify(rows))});
check('unchanged needs no writes',()=>{const clone=structuredClone(rows);clone[3].fields['收支']='120.00';assert.equal(ctx.ledgerPlan_(clone).length,0)});
check('duplicates stop',()=>{const clone=structuredClone(rows);clone.push({...clone[3],record_id:'duplicate'});assert.throws(()=>ctx.ledgerPlan_(clone))});
check('removed last detail resets transfer',()=>{assert.equal(ctx.ledgerPlan_([rows[3]])[0].after,0)});
check('manual same-name transfer protected',()=>{const clone=structuredClone(rows);clone[3].fields['来源']='手动';assert.throws(()=>ctx.ledgerPlan_(clone))});
check('month mismatch detected',()=>{const clone=structuredClone(rows);clone[0].fields['月份']=[{text:'2026/09'}];assert.throws(()=>ctx.ledgerPlan_(clone))});
check('formula-looking memo remains literal',()=>{const cell=ctx.ledgerCell_('=1+1');assert.equal(cell.userEnteredValue.stringValue,'=1+1');assert.equal(cell.userEnteredValue.formulaValue,undefined)});
check('successful one-batch mirror and readback',()=>{rows[3].fields['收支']='120.00';const result=ctx.ledgerBackup_({properties:props},rows);assert.equal(batchCalls,1);assert.equal(result.records,4);assert.equal(store.get('LAST_SUCCESS_COUNT'),'4');assert.equal(tableMap.get('明细').data.length,5)});
check('failed batch retains previous data and success marker',()=>{const old=JSON.stringify(tableMap.get('明细').data),last=store.get('LAST_SUCCESS_HASH');forceFailure=true;assert.throws(()=>ctx.ledgerBackup_({properties:props},[...rows,r('new','1')]));assert.equal(JSON.stringify(tableMap.get('明细').data),old);assert.equal(store.get('LAST_SUCCESS_HASH'),last);forceFailure=false});
check('large shrink blocks publishing',()=>{const n=batchCalls;store.set('LAST_SUCCESS_COUNT','100');assert.throws(()=>ctx.ledgerBackup_({properties:props},rows));assert.equal(batchCalls,n)});
console.log(`${checks} offline cloud checks passed. New generic deployment and iPhone runtime are not exercised by these offline tests.`);
check('negative automatic transfer is negative life income, not life expense',()=>{
  const row=r('loss',-25,'生活','生意结余','自动联动','2026/10 生意净结余（自动联动）');
  const cells=ctx.ledgerRows_([row])[0];assert.equal(cells[7],-25);assert.equal(cells[8],0);
});
check('empty new ledger backs up a header, existing backup cannot shrink to empty',()=>{
  store.set('LAST_SUCCESS_COUNT','100');assert.throws(()=>ctx.ledgerBackup_({properties:props},[]));
  store.delete('LAST_SUCCESS_COUNT');assert.equal(ctx.ledgerBackup_({properties:props},[]).records,0);
});
check('core has no Sheets dependency or Sheets scope',()=>{
  assert(!/SpreadsheetApp|Sheets\./.test(core));
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'apps-script/appsscript.json')));
  assert(!manifest.oauthScopes.some(s=>s.includes('spreadsheets')));
});
check('configuration is pinned; switching tables requires a fresh project',()=>{
  store.set('FEISHU_APP_ID','cli_example');store.set('FEISHU_APP_TOKEN','ExampleBase');store.set('FEISHU_TABLE_ID','tblExample');
  assert.equal(ctx.ledgerConfig_().tableId,'tblExample');store.set('FEISHU_TABLE_ID','tblOther');assert.throws(()=>ctx.ledgerConfig_());store.set('FEISHU_TABLE_ID','tblExample');
});
const originalRequest=ctx.ledgerRequest_;
check('pagination reads every page and rejects repeated/missing cursors',()=>{
  let page=0;ctx.ledgerRequest_=()=>({data:++page===1?{items:[r('a',1)],total:2,has_more:true,page_token:'next'}:{items:[r('b',2)],total:2,has_more:false}});
  assert.equal(ctx.ledgerRead_({prefix:'/test'}).length,2);
  ctx.ledgerRequest_=()=>({data:{items:[],has_more:true,page_token:'same'}});assert.throws(()=>ctx.ledgerRead_({prefix:'/test'}));
  ctx.ledgerRequest_=()=>({data:{}});assert.throws(()=>ctx.ledgerRead_({prefix:'/test'}));ctx.ledgerRequest_=originalRequest;
});
check('schema mismatch blocks writes',()=>{
  ctx.ledgerRequest_=()=>({data:{items:[{field_name:'收支',type:1}],has_more:false}});
  assert.throws(()=>ctx.ledgerValidate_({prefix:'/test'}));ctx.ledgerRequest_=originalRequest;
});
check('uncertain creates remain journaled and are not repeated on the next run',()=>{
  const originalRead=ctx.ledgerRead_;
  const input=[r('biz',10)];let creates=0;
  ctx.ledgerRead_=()=>structuredClone(input);
  ctx.ledgerRequest_=(path,method)=>{if(method==='post'){creates++;throw Error('response lost')}throw Error('unexpected request')};
  store.delete('PENDING_CREATES');
  assert.throws(()=>ctx.ledgerReconcile_({properties:props,prefix:'/test'},input));assert.equal(creates,1);
  assert(JSON.parse(store.get('PENDING_CREATES'))['2026/10']);
  assert.throws(()=>ctx.ledgerReconcile_({properties:props,prefix:'/test'},input));assert.equal(creates,1);
  ctx.ledgerRead_=originalRead;ctx.ledgerRequest_=originalRequest;store.delete('PENDING_CREATES');
});
check('default core run works without any Google Sheets globals',()=>{
  const coreCtx={...ctx};delete coreCtx.SpreadsheetApp;delete coreCtx.Sheets;delete coreCtx.ledgerBackup_;
  vm.createContext(coreCtx);vm.runInContext(core,coreCtx);
  const good=[r('source',10),r('transfer',10,'生活','生意结余','自动联动','2026/10 生意净结余（自动联动）')];
  coreCtx.ledgerSession_=()=>({properties:props});coreCtx.ledgerValidate_=()=>{};coreCtx.ledgerRead_=()=>good;
  coreCtx.LockService={getScriptLock:()=>({tryLock:()=>true,releaseLock(){}})};
  store.set('CLOUD_WRITES_ENABLED','true');store.delete('BACKUP_ENABLED');
  assert.equal(coreCtx.runDailySync().backup,'disabled');assert(store.get('LAST_RUN_SUCCESS_AT'));
  store.set('BACKUP_ENABLED','true');assert.throws(()=>coreCtx.runDailySync());store.delete('BACKUP_ENABLED');
});
check('daily trigger installer replaces only its own handler',()=>{
  const removed=[],created=[];store.set('LAST_RUN_SUCCESS_AT','fixture');store.set('CLOUD_WRITES_ENABLED','true');
  let own={getHandlerFunction:()=> 'runDailySync'},other={getHandlerFunction:()=> 'unrelatedJob'};
  const chain={timeBased(){return this},atHour(n){assert.equal(n,3);return this},nearMinute(n){assert.equal(n,30);return this},everyDays(n){assert.equal(n,1);return this},inTimezone(t){assert.equal(t,'Asia/Shanghai');return this},create(){created.push(true)}};
  ctx.ScriptApp={getProjectTriggers:()=>[own,other],deleteTrigger:t=>removed.push(t),newTrigger:fn=>{assert.equal(fn,'runDailySync');return chain}};
  ctx.installDailyTrigger();assert.equal(removed.length,1);assert.equal(removed[0],own);assert.equal(created.length,1);
});
console.log(`${checks} total offline cloud checks passed.`);
