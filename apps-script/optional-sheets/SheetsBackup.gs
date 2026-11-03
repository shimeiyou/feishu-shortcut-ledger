// Optional module. Install ONLY when BACKUP_ENABLED=true. Uses Sheets v4.
const LEDGER_HEADER = ["时间", "事件", "收支", "账本", "分类", "来源", "月份", "收入", "支出", "record_id"];
function ledgerRows_(records) {
  return records.slice().sort((a,b)=>b.fields['时间']-a.fields['时间']||a.record_id.localeCompare(b.record_id)).map(r=>{
    const f=r.fields, cents=ledgerCents_(f['收支']);
    if (!ledgerText_(f['事件']).trim() || !['生意','生活'].includes(ledgerText_(f['账本'])) || !ledgerText_(f['分类'])) throw Error('必填字段缺失或账本异常');
    return [Utilities.formatDate(new Date(f['时间']),'Asia/Shanghai','yyyy/MM/dd HH:mm:ss'),ledgerText_(f['事件']),cents/100,
      ledgerText_(f['账本']),ledgerText_(f['分类']),ledgerText_(f['来源']),ledgerMonth_(f),(ledgerAutoMonth_(r)?cents:Math.max(cents,0))/100,(ledgerAutoMonth_(r)?0:Math.max(-cents,0))/100,r.record_id];
  });
}
function ledgerCell_(v) {
  if (v===null || v==='') return {};
  if (v instanceof Date) return {userEnteredValue:{numberValue:v.getTime()/86400000+25569}};
  if (typeof v==='number') {if (!Number.isFinite(v)) throw Error('无效数值');return {userEnteredValue:{numberValue:v}};}
  return {userEnteredValue:{stringValue:v instanceof Date?Utilities.formatDate(v,'Asia/Shanghai','yyyy/MM/dd HH:mm:ss'):String(v)}};
}
function ledgerBackup_(s,records) {
  const rows=ledgerRows_(records), hash=ledgerHash_(rows), ss=SpreadsheetApp.openById(s.properties.getProperty('SPREADSHEET_ID'));
  const previousCount=Number(s.properties.getProperty('LAST_SUCCESS_COUNT')||0);
  if (previousCount && rows.length<previousCount*0.8 && s.properties.getProperty('ALLOW_LARGE_SHRINK')!=='true') throw Error('记录数量骤降超过20%，需核对后允许本轮缩水');
  const now=Utilities.formatDate(new Date(),'Asia/Shanghai','yyyy/MM/dd HH:mm:ss');
  const existing=ss.getSheetByName('明细');
  const prior=existing && existing.getLastRow()?existing.getRange(1,1,existing.getLastRow(),Math.min(10,existing.getMaxColumns())).getValues():[];
  const groups={'明细':[LEDGER_HEADER,...rows],
    '生意':[LEDGER_HEADER,...rows.filter(r=>r[3]==='生意')],
    '生活':[LEDGER_HEADER,...rows.filter(r=>r[3]==='生活')],
    '自动联动':[LEDGER_HEADER,...rows.filter(r=>r[3]==='生活' && r[4]==='生意结余' && r[5]==='自动联动')],
    '说明':[['项目','值'],['最后成功备份时间（北京时间）',now],['记录数',rows.length],['快照摘要',hash],['来源','飞书一体账本，单向备份'],['执行方式','Google 云端每天一次'],['统计说明','跨账本统计请排除自动结余，避免内部流转重复计入收入']]};
  // Retain one prior successful mirror. More history can be added separately.
  if (prior.length) groups['云端备份_上一份明细']=prior;
  const requests=[];
  Object.entries(groups).forEach(([name,data])=>{
    const sheet=ss.getSheetByName(name)||ss.insertSheet(name), cols=Math.max(...data.map(r=>r.length));
    if (sheet.getMaxRows()<data.length) requests.push({appendDimension:{sheetId:sheet.getSheetId(),dimension:'ROWS',length:data.length-sheet.getMaxRows()}});
    if (sheet.getMaxColumns()<cols) requests.push({appendDimension:{sheetId:sheet.getSheetId(),dimension:'COLUMNS',length:cols-sheet.getMaxColumns()}});
    requests.push({updateCells:{range:{sheetId:sheet.getSheetId(),startRowIndex:0,startColumnIndex:0,endRowIndex:Math.max(data.length,sheet.getLastRow()),endColumnIndex:cols},
      rows:data.map(row=>({values:row.map(ledgerCell_)})),fields:'userEnteredValue'}});
  });
  Sheets.Spreadsheets.batchUpdate({requests},ss.getId());
  SpreadsheetApp.flush();
  const readback=rows.length?ss.getSheetByName('明细').getRange(2,1,rows.length,10).getValues():[];
  if (ledgerHash_(readback)!==hash) throw Error('Google 回读核验失败，未标记本轮成功');
  s.properties.setProperties({LAST_BACKUP_SUCCESS_AT:now,LAST_SUCCESS_COUNT:String(rows.length),LAST_SUCCESS_HASH:hash});
  s.properties.deleteProperty('ALLOW_LARGE_SHRINK');
  return {records:rows.length,sha256:hash,lastSuccessAt:now};
}
