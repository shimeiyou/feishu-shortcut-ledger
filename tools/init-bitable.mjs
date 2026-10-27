#!/usr/bin/env node
/**
 * init-bitable.mjs — Zero-dependency Feishu Bitable (多维表格) Schema & Formula Initializer
 *
 * Requires: Node.js 18+ (uses built-in global `fetch`).
 * Creates one or two ledger tables inside your Feishu Bitable base with the exact
 * Bookkeeping Schema:
 *   Base Fields (written by iPhone Shortcut / API):
 *     1. 事件 (Text, type=1, primary column) — 消费或收入摘要
 *     2. 收支 (Number, type=2, 2 decimals)   — 正数表示收入（如 500），负数表示支出（如 -35.5）
 *     3. 标签 (Text, type=1)                 — 通用分类文本标签
 *     4. 分类 (Multi-Select, type=4)         — 彩色分类标签（餐饮、交通、购物、副业收入、采购成本等）
 *     5. 时间 (Date, type=5, yyyy/MM/dd)     — 记账日期（开启新记录自动填入创建时间）
 *     6. 渠道 (Text, type=1)                 — 微信支付 / 支付宝 / 银行卡 / 现金（可选）
 *   Formula Fields (type=20, auto-calculated for the 8 Dashboard Widgets):
 *     7. 收入 (Formula) — IF([收支]>0,[收支],0)
 *     8. 支出 (Formula) — IF([收支]<0,ABS([收支]),0)
 *     9. 月份 (Formula) — TEXT([时间],"YYYY/MM")
 *
 * Usage:
 *   FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx FEISHU_APP_TOKEN=bascnxxx node tools/init-bitable.mjs
 *   node tools/init-bitable.mjs --dry-run
 *   node tools/init-bitable.mjs --app-id cli_xxx --app-secret xxx --app-token bascnxxx --insert-sample
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

function parseArgs(argv) {
  const args = {
    appId: process.env.FEISHU_APP_ID || '',
    appSecret: process.env.FEISHU_APP_SECRET || '',
    appToken: process.env.FEISHU_APP_TOKEN || '',
    appTokenBiz: process.env.FEISHU_APP_TOKEN_BIZ || '',
    appTokenLife: process.env.FEISHU_APP_TOKEN_LIFE || '',
    mode: process.env.LEDGER_MODE || 'dual', // 'dual' | 'single'
    insertSample: false,
    dryRun: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--dry-run') args.dryRun = true;
    else if (a === '--insert-sample') args.insertSample = true;
    else if (a === '--app-id') args.appId = argv[++i] || '';
    else if (a === '--app-secret') args.appSecret = argv[++i] || '';
    else if (a === '--app-token') args.appToken = argv[++i] || '';
    else if (a === '--app-token-biz') args.appTokenBiz = argv[++i] || '';
    else if (a === '--app-token-life') args.appTokenLife = argv[++i] || '';
    else if (a === '--mode') args.mode = argv[++i] || 'dual';
    else if (a === '--help' || a === '-h') {
      console.log(`Usage:
  FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx FEISHU_APP_TOKEN=bascnxxx node tools/init-bitable.mjs [options]

Options:
  --app-id <id>            Feishu App ID (or env FEISHU_APP_ID)
  --app-secret <secret>    Feishu App Secret (or env FEISHU_APP_SECRET)
  --app-token <token>      Bitable App Token from URL (or env FEISHU_APP_TOKEN)
  --app-token-biz <token>  Optional separate Bitable App Token for Business/Project Ledger
  --app-token-life <token> Optional separate Bitable App Token for Daily Life Ledger
  --mode <dual|single>     Create two tables ('日常消费账本' + '副业项目账本') or one table (default: dual)
  --insert-sample          Insert sample records from config/sample-records.json after table creation
  --dry-run                Print the exact REST API payloads without making network requests`);
      process.exit(0);
    }
  }
  return args;
}

const LIFE_CATEGORIES = [
  { name: '餐饮' },
  { name: '交通' },
  { name: '购物' },
  { name: '居住水电' },
  { name: '娱乐休闲' },
  { name: '医疗健康' },
  { name: '人情往来' },
  { name: '其他消费' },
  { name: '主业工资' },
  { name: '奖金补贴' },
  { name: '理财收益' },
  { name: '闲置转让' },
  { name: '其他收入' },
  { name: '生意结余' },
];

const BIZ_CATEGORIES = [
  { name: '主业收入' },
  { name: '副业收入' },
  { name: '项目回款' },
  { name: '咨询服务' },
  { name: '采购成本' },
  { name: '运营支出' },
  { name: '软件云服务' },
  { name: '办公耗材' },
  { name: '交通物流' },
  { name: '设备工具' },
  { name: '其他支出' },
];

/**
 * Build the Feishu Bitable `tables.create` payload with base fields,
 * plus subsequent `fields.create` payloads for formula columns.
 */
function buildTableSchema(tableName, categoryOptions, isLifeLedger = false) {
  const baseFields = [
    {
      field_name: '事件',
      type: 1, // Text (Primary column)
    },
    {
      field_name: '收支',
      type: 2, // Number (+income, -expense)
      property: {
        formatter: '0.00',
      },
    },
    {
      field_name: '标签',
      type: 1, // Text
    },
    {
      field_name: '分类',
      type: 4, // MultiSelect (compatible with array ["分类"] from iOS Shortcut)
      property: {
        options: categoryOptions,
      },
    },
    {
      field_name: '时间',
      type: 5, // DateTime
      property: {
        date_formatter: 'yyyy/MM/dd',
        auto_fill: true,
      },
    },
    {
      field_name: '渠道',
      type: 1, // Text (微信支付 / 支付宝 / 银行卡 / 现金)
    },
  ];

  const incomeFormula = isLifeLedger
    ? 'IF([标签]="生意结余",[收支],IF([收支]>0,[收支],0))'
    : 'IF([收支]>0,[收支],0)';
  const expenseFormula = isLifeLedger
    ? 'IF([标签]="生意结余",0,IF([收支]<0,ABS([收支]),0))'
    : 'IF([收支]<0,ABS([收支]),0)';

  const formulaFields = [
    {
      field_name: '收入',
      type: 20, // Formula
      property: {
        formula_expression: incomeFormula,
        formatter: '0.00',
      },
    },
    {
      field_name: '支出',
      type: 20, // Formula
      property: {
        formula_expression: expenseFormula,
        formatter: '0.00',
      },
    },
    {
      field_name: '月份',
      type: 20, // Formula
      property: {
        formula_expression: 'TODATE([时间],"YYYY/MM")',
      },
    },
  ];

  return {
    tablePayload: {
      table: {
        name: tableName,
        default_view_name: '收支明细表',
        fields: baseFields,
      },
    },
    formulaFields,
  };
}

async function feishuRequest(url, method, token, body) {
  const headers = { 'Content-Type': 'application/json; charset=utf-8' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await res.json();
  if (!res.ok || (typeof json.code === 'number' && json.code !== 0)) {
    throw new Error(`Feishu API error (${method} ${url}) -> code=${json.code} msg=${json.msg || res.statusText}`);
  }
  return json.data;
}

async function getTenantAccessToken(appId, appSecret) {
  const data = await feishuRequest(
    'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    'POST',
    null,
    { app_id: appId, app_secret: appSecret }
  );
  // Note: tenant_access_token response puts tenant_access_token at top-level
  return data?.tenant_access_token;
}

async function fetchTenantTokenRaw(appId, appSecret) {
  const res = await fetch('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ app_id: appId, app_secret: appSecret }),
  });
  const json = await res.json();
  if (json.code !== 0 || !json.tenant_access_token) {
    throw new Error(`Failed to get tenant_access_token: code=${json.code} msg=${json.msg}`);
  }
  return json.tenant_access_token;
}

async function createLedgerTable(token, appToken, tableName, categoryOptions, isLifeLedger = false) {
  const { tablePayload, formulaFields } = buildTableSchema(tableName, categoryOptions, isLifeLedger);
  const createUrl = `https://open.feishu.cn/open-apis/bitable/v1/apps/${appToken}/tables`;
  console.log(`\n[1/2] Creating table "${tableName}" in Bitable app ${appToken}...`);
  const data = await feishuRequest(createUrl, 'POST', token, tablePayload);
  const tableId = data.table_id;
  console.log(`  -> Created table_id: ${tableId}`);

  console.log(`[2/2] Adding 3 auto-calculated Formula fields (收入, 支出, 月份) to ${tableId}...`);
  const fieldUrl = `https://open.feishu.cn/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/fields`;
  for (const ff of formulaFields) {
    await feishuRequest(fieldUrl, 'POST', token, ff);
    console.log(`  -> Created formula field: ${ff.field_name} = ${ff.property.formula_expression}`);
  }

  return {
    tableName,
    appToken,
    tableId,
    recordUrl: `https://open.feishu.cn/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/records`,
  };
}

async function insertSampleRecords(token, appToken, tableId, records) {
  const batchUrl = `https://open.feishu.cn/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/records/batch_create`;
  const payload = {
    records: records.map((r) => ({
      fields: {
        事件: r['事件'],
        收支: r['收支'],
        标签: r['标签'],
        分类: r['分类'],
        时间: Date.parse(r['时间'].replace(/\//g, '-') + 'T12:00:00+08:00'),
        渠道: r['渠道'],
      },
    })),
  };
  await feishuRequest(batchUrl, 'POST', token, payload);
  console.log(`  -> Inserted ${records.length} sample records into ${tableId}`);
}

async function main() {
  const args = parseArgs(process.argv);
  const lifeToken = args.appTokenLife || args.appToken || 'YOUR_BITABLE_APP_TOKEN_LIFE';
  const bizToken = args.appTokenBiz || args.appToken || 'YOUR_BITABLE_APP_TOKEN_BIZ';

  if (args.dryRun) {
    console.log('=== [DRY RUN] Feishu Bitable Initialization Payloads ===\n');
    const bizSchema = buildTableSchema('副业项目账本', BIZ_CATEGORIES, false);
    const lifeSchema = buildTableSchema('日常消费账本', LIFE_CATEGORIES, true);
    console.log('1. POST /open-apis/bitable/v1/apps/:app_token/tables (副业项目账本):');
    console.log(JSON.stringify(bizSchema.tablePayload, null, 2));
    console.log('\n2. POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/fields (3 Formula Fields):');
    console.log(JSON.stringify(bizSchema.formulaFields, null, 2));
    console.log('\n3. POST /open-apis/bitable/v1/apps/:app_token/tables (日常消费账本):');
    console.log(JSON.stringify(lifeSchema.tablePayload, null, 2));
    console.log('\n4. POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/fields (日常消费账本 联动公式列):');
    console.log(JSON.stringify(lifeSchema.formulaFields, null, 2));
    console.log('\n[DRY RUN OK] No network calls made.');
    return;
  }

  if (!args.appId || !args.appSecret || (!args.appToken && (!args.appTokenBiz || !args.appTokenLife))) {
    console.error('Error: Missing required credentials. Provide FEISHU_APP_ID, FEISHU_APP_SECRET, and FEISHU_APP_TOKEN (or run with --dry-run).');
    process.exit(1);
  }

  const token = await fetchTenantTokenRaw(args.appId, args.appSecret);
  const sampleData = JSON.parse(fs.readFileSync(path.join(ROOT, 'config', 'sample-records.json'), 'utf8'));

  const bizRes = await createLedgerTable(token, bizToken, '副业项目账本', BIZ_CATEGORIES);
  let lifeRes = bizRes;
  if (args.mode === 'dual') {
    lifeRes = await createLedgerTable(token, lifeToken, '日常消费账本', LIFE_CATEGORIES, true);
  }

  if (args.insertSample) {
    await insertSampleRecords(token, bizRes.appToken, bizRes.tableId, sampleData.biz_records);
    if (args.mode === 'dual') {
      await insertSampleRecords(token, lifeRes.appToken, lifeRes.tableId, sampleData.life_records);
    }
  }

  console.log('\n============================================================');
  console.log('Feishu Bitable Initialization Complete!');
  console.log('Copy these Record API URLs into your iPhone Shortcut:');
  console.log(`  biz_url : ${bizRes.recordUrl}`);
  console.log(`  life_url: ${lifeRes.recordUrl}`);
  console.log('============================================================\n');
}

main().catch((err) => {
  console.error('[FATAL]', err.message);
  process.exit(1);
});
