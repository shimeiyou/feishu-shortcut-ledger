// Unified ledger v2. No personal configuration or public webhook.
// Required Script Properties: FEISHU_APP_ID, FEISHU_APP_SECRET,
// FEISHU_APP_TOKEN, FEISHU_TABLE_ID. BACKUP_ENABLED defaults to false.
function ledgerConfig_() {
  const p=PropertiesService.getScriptProperties();
  const cfg={appId:p.getProperty('FEISHU_APP_ID'),appToken:p.getProperty('FEISHU_APP_TOKEN'),tableId:p.getProperty('FEISHU_TABLE_ID')};
  if (!/^cli_[A-Za-z0-9]+$/.test(cfg.appId||'') || !/^[A-Za-z0-9]+$/.test(cfg.appToken||'') || !/^tbl[A-Za-z0-9]+$/.test(cfg.tableId||'')) throw Error('请填写有效的 FEISHU_APP_ID / FEISHU_APP_TOKEN / FEISHU_TABLE_ID');
  const target=JSON.stringify(cfg), pinned=p.getProperty('PINNED_TARGET');
  if (pinned && pinned!==target) throw Error('目标表已变化；请新建项目并重新预演，避免使用旧同步状态');
  if (!pinned) p.setProperty('PINNED_TARGET',target);
  return cfg;
}
function ledgerValidate_(s) {
  const expected={'事件':1,'时间':5,'收支':2,'账本':3,'分类':3,'来源':1,'月份':20,'收入':20,'支出':20};
  const found={}; let cursor=null; const seen=new Set();
  do {
    const d=ledgerRequest_(s.prefix+'/fields?page_size=100'+(cursor?'&page_token='+encodeURIComponent(cursor):''),'get',undefined,s.token).data;
    if (!Array.isArray(d?.items)) throw Error('字段响应不完整');
    d.items.forEach(f=>found[f.field_name]=f.type);
    if (!d.has_more) break;
    cursor=d.page_token;if(!cursor||seen.has(cursor))throw Error('字段分页异常');seen.add(cursor);
  } while(true);
  Object.entries(expected).forEach(([n,t])=>{if(found[n]!==t)throw Error('字段类型不匹配：'+n+'，需要 v2 一体账本结构');});
}
function ledgerText_(v) {
  if (v == null) return '';
  if (Array.isArray(v)) return v.map(ledgerText_).join('');
  if (typeof v === 'object') return ledgerText_(v.text ?? v.value ?? v.name ?? '');
  return String(v);
}
function ledgerCents_(v) {
  if (v == null || typeof v === 'boolean') throw Error('金额缺失或格式不正确');
  const s=String(v), match=/^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(s);
  if (!match) throw Error('金额必须是最多两位小数的有限数字');
  const n=(Number(match[2])*100+Number((match[3]||'').padEnd(2,'0')))*(match[1]?-1:1);
  if (!Number.isSafeInteger(n)) throw Error('金额超出安全范围');
  return n;
}
function ledgerMonth_(f) {
  if (typeof f['时间']!=='number' || !Number.isFinite(f['时间'])) throw Error('时间缺失');
  const m=Utilities.formatDate(new Date(f['时间']),'Asia/Shanghai','yyyy/MM');
  const formula=ledgerText_(f['月份']);
  if (formula && formula!==m) throw Error('月份公式与时间不一致');
  return m;
}
function ledgerTitle_(m) { return m+' 生意净结余（自动联动）'; }
function ledgerAutoMonth_(r) {
  const f=r.fields, title=ledgerText_(f['事件']);
  const exact=ledgerText_(f['账本'])==='生活' && ledgerText_(f['分类'])==='生意结余' && ledgerText_(f['来源'])==='自动联动';
  if (!exact) return null;
  const match=/^(\d{4}\/\d{2}) 生意净结余（自动联动）$/.exec(title);
  if (!match || ledgerMonth_(f)!==match[1]) throw Error('自动联动记录标识或日期异常：'+r.record_id);
  return match[1];
}
function ledgerPlan_(records) {
  const sums={}, autos={};
  records.forEach(r=>{
    const f=r.fields;
    if (!r.record_id || !f || !['生意','生活'].includes(ledgerText_(f['账本'])) || !ledgerText_(f['事件']).trim() || !ledgerText_(f['分类'])) throw Error('记录必填字段或账本异常');
    ledgerMonth_(f); ledgerCents_(f['收支']);
    if (ledgerText_(f['账本'])==='生意') {
      const m=ledgerMonth_(f); sums[m]=(sums[m]||0)+ledgerCents_(f['收支']);
      if (!Number.isSafeInteger(sums[m])) throw Error('月合计超出安全范围');
    }
    const m=ledgerAutoMonth_(r);
    if (m) { if (autos[m]) throw Error('同月自动汇总重复，停止写入：'+m); autos[m]=r; }
    else if (ledgerText_(f['账本'])==='生活' && /^\d{4}\/\d{2} 生意净结余（自动联动）$/.test(ledgerText_(f['事件']))) throw Error('存在非自动来源的同名汇总，需人工核对');
  });
  return [...new Set([...Object.keys(sums),...Object.keys(autos)])].sort().flatMap(m=>{
    const n=sums[m]||0, r=autos[m], before=r?ledgerCents_(r.fields['收支']):null;
    return before===n?[]:[{month:m,recordId:r?.record_id||null,before,after:n}];
  });
}
function ledgerHash_(v) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,JSON.stringify(v),Utilities.Charset.UTF_8).map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
}
function ledgerFingerprint_(rows) {
  // Explicit fields yield stable ordering independent of API object-key order.
  return ledgerHash_(rows.map(r=>[r.record_id,...['时间','事件','收支','账本','分类','来源','月份'].map(k=>ledgerText_(r.fields[k]))]).sort((a,b)=>a[0].localeCompare(b[0])));
}
function ledgerRequest_(path,method,body,token) {
  const options={method:method||'get',contentType:'application/json',muteHttpExceptions:true,headers:{}};
  if (token) options.headers.Authorization='Bearer '+token;
  if (body!==undefined) options.payload=JSON.stringify(body);
  const response=UrlFetchApp.fetch('https://open.feishu.cn/open-apis'+path,options);
  const status=response.getResponseCode();
  if (status<200 || status>=300) throw Error('飞书接口 HTTP '+status+'，本轮中止');
  const data=JSON.parse(response.getContentText());
  if (data.code!==0) throw Error('飞书业务错误 '+data.code+'，本轮中止');
  return data;
}
function ledgerSession_() {
  const properties=PropertiesService.getScriptProperties(), cfg=ledgerConfig_();
  const secret=properties.getProperty('FEISHU_APP_SECRET');
  if (!secret) throw Error('请在脚本属性中配置 FEISHU_APP_SECRET');
  const token=ledgerRequest_('/auth/v3/tenant_access_token/internal','post',{app_id:cfg.appId,app_secret:secret}).tenant_access_token;
  if (!token) throw Error('没有获得授权令牌');
  return {token,prefix:'/bitable/v1/apps/'+encodeURIComponent(cfg.appToken)+'/tables/'+cfg.tableId,properties};
}
function ledgerRead_(s) {
  let rows=[], cursor=null; const seen=new Set(), totals=[];
  do {
    let path=s.prefix+'/records?page_size=500'; if (cursor) path+='&page_token='+encodeURIComponent(cursor);
    const d=ledgerRequest_(path,'get',undefined,s.token).data;
    if (!Array.isArray(d?.items) || typeof d.has_more!=='boolean') throw Error('记录响应不完整');
    if (d.items.some(r=>!r.record_id||!r.fields)) throw Error('记录标识缺失');
    rows=rows.concat(d.items); if (d.total!==undefined) totals.push(d.total);
    if (!d.has_more) break;
    cursor=d.page_token;
    if (!cursor || seen.has(cursor)) throw Error('分页不完整或游标重复');
    seen.add(cursor);
  } while (true);
  if (new Set(rows.map(r=>r.record_id)).size!==rows.length || totals.some(n=>n!==rows.length)) throw Error('记录数量或分页校验失败');
  return rows;
}
function previewDailySync() {
  const s=ledgerSession_(); ledgerValidate_(s);
  const rows=ledgerRead_(s), changes=ledgerPlan_(rows);
  const report={mode:'preview',records:rows.length,changes:changes.map(c=>({...c,before:c.before===null?null:c.before/100,after:c.after/100})),message:'未修改飞书或 Sheets'};
  console.log(JSON.stringify(report)); return report;
}
function ledgerReconcile_(s,rows) {
  const pending=JSON.parse(s.properties.getProperty('PENDING_CREATES')||'{}');
  const existing=new Set(rows.map(ledgerAutoMonth_).filter(Boolean));
  Object.keys(pending).forEach(m=>{if (!existing.has(m)) throw Error('上次创建结果待核实，禁止重复创建：'+m); delete pending[m];});
  s.properties.setProperty('PENDING_CREATES',JSON.stringify(pending));
  const changes=ledgerPlan_(rows), second=ledgerRead_(s);
  if (ledgerFingerprint_(rows)!==ledgerFingerprint_(second)) throw Error('读取期间数据变化，请稍后重试');
  const businessHash=rs=>ledgerFingerprint_(rs.filter(r=>ledgerText_(r.fields['账本'])==='生意'));
  const originalBusiness=businessHash(rows);
  for (const change of changes) {
    const latest=ledgerRead_(s);
    if (ledgerFingerprint_(latest)!==ledgerFingerprint_(rows)) throw Error('写入前数据变化，本轮中止');
    let rid=change.recordId;
    if (rid) ledgerRequest_(s.prefix+'/records/'+rid,'put',{fields:{'收支':change.after/100}},s.token);
    else {
      pending[change.month]={at:new Date().toISOString(),amount:change.after};
      s.properties.setProperty('PENDING_CREATES',JSON.stringify(pending));
      const fields={'事件':ledgerTitle_(change.month),'收支':change.after/100,'账本':'生活','分类':'生意结余','来源':'自动联动',
        '时间':Date.parse(change.month.replace('/','-')+'-01T12:00:00+08:00')};
      const response=ledgerRequest_(s.prefix+'/records','post',{fields},s.token);
      rid=response.data?.record?.record_id;
      if (!rid) throw Error('创建结果待核实，请勿重复提交');
    }
    const checked=ledgerRequest_(s.prefix+'/records/'+rid,'get',undefined,s.token).data.record;
    if (ledgerAutoMonth_(checked)!==change.month || ledgerCents_(checked.fields['收支'])!==change.after) throw Error('写后回读不一致');
    rows=ledgerRead_(s);
    if (!change.recordId) { delete pending[change.month];s.properties.setProperty('PENDING_CREATES',JSON.stringify(pending)); }
    if (businessHash(rows)!==originalBusiness) throw Error('执行期间生意明细变化，请重新运行');
  }
  if (ledgerPlan_(rows).length) throw Error('月结余尚有差异，暂不备份');
  return rows;
}
function runDailySync() {
  const lock=LockService.getScriptLock();
  if (!lock.tryLock(1000)) throw Error('已有云端同步在执行');
  const props=PropertiesService.getScriptProperties();
  try {
    if (props.getProperty('CLOUD_WRITES_ENABLED')!=='true') throw Error('先预演并暂停其他写入器，再将 CLOUD_WRITES_ENABLED 设为 true');
    const backup=props.getProperty('BACKUP_ENABLED')==='true';
    if (backup && typeof ledgerBackup_!=='function') throw Error('先安装可选 SheetsBackup.gs 和 Sheets v4 服务');
    const s=ledgerSession_(); ledgerValidate_(s);
    const rows=ledgerReconcile_(s,ledgerRead_(s));
    const result=backup?ledgerBackup_(s,rows):{records:rows.length,backup:'disabled'};
    props.setProperty('LAST_RUN_SUCCESS_AT',new Date().toISOString());props.deleteProperty('LAST_ERROR');
    console.log(JSON.stringify({ok:true,...result}));return result;
  } catch(e) {props.setProperty('LAST_ERROR',new Date().toISOString()+' '+e.message);throw e;}
  finally {lock.releaseLock();}
}
function installDailyTrigger() {
  const props=PropertiesService.getScriptProperties();
  if (!props.getProperty('LAST_RUN_SUCCESS_AT') || props.getProperty('CLOUD_WRITES_ENABLED')!=='true') throw Error('必须先手动成功运行一次 runDailySync');
  ScriptApp.getProjectTriggers().filter(t=>t.getHandlerFunction()==='runDailySync').forEach(t=>ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('runDailySync').timeBased().atHour(3).nearMinute(30).everyDays(1).inTimezone('Asia/Shanghai').create();
  console.log('已安装每日约03:30北京时间任务，时间可前后浮动15分钟。');
}
