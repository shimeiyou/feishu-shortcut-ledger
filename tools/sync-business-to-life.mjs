#!/usr/bin/env node
/**
 * sync-business-to-life.mjs — Dual-Ledger Monthly Net Balance Auto-Sync (Plan A)
 *
 * Aggregates all records in the Business/Side-Hustle Ledger by month (YYYY/MM in UTC+8),
 * calculates SUM(收支) rounded to 2 decimal places, and idempotently upserts each month's
 * net balance row into the Daily Life Expense Ledger:
 *   - Match key: 标签 == "生意结余" && 事件 starts with "YYYY/MM"
 *   - Row format:
 *       事件: "YYYY/MM 生意净结余（自动联动）"
 *       收支: round(SUM(收支), 2)
 *       标签: "生意结余"
 *       分类: ["生意结余"]
 *       渠道: "生意账本自动同步"
 *       时间: 1st of YYYY/MM 12:00:00 (UTC+8) in ms timestamp
 *   - Zero writes when a month's net balance is already up to date.
 *
 * Paired with the upgraded Life Ledger formulas:
 *   - 收入: IF([标签]="生意结余",[收支],IF([收支]>0,[收支],0))
 *   - 支出: IF([标签]="生意结余",0,IF([收支]<0,ABS([收支]),0))
 *
 * Usage:
 *   FEISHU_APP_ID=cli_xxx \
 *   FEISHU_APP_SECRET=xxx \
 *   FEISHU_BIZ_APP_TOKEN=bascnBiz \
 *   FEISHU_BIZ_TABLE_ID=tblBiz \
 *   FEISHU_LIFE_APP_TOKEN=bascnLife \
 *   FEISHU_LIFE_TABLE_ID=tblLife \
 *   node tools/sync-business-to-life.mjs [--dry-run]
 */

function parseArgs(argv) {
  const args = {
    apiBase: (process.env.FEISHU_API_BASE || 'https://open.feishu.cn').replace(/\/+$/, ''),
    appId: process.env.FEISHU_APP_ID || '',
    appSecret: process.env.FEISHU_APP_SECRET || '',
    bizAppToken: process.env.FEISHU_BIZ_APP_TOKEN || process.env.FEISHU_APP_TOKEN_BIZ || process.env.FEISHU_APP_TOKEN || '',
    bizTableId: process.env.FEISHU_BIZ_TABLE_ID || process.env.FEISHU_TABLE_ID_BIZ || '',
    lifeAppToken: process.env.FEISHU_LIFE_APP_TOKEN || process.env.FEISHU_APP_TOKEN_LIFE || process.env.FEISHU_APP_TOKEN || '',
    lifeTableId: process.env.FEISHU_LIFE_TABLE_ID || process.env.FEISHU_TABLE_ID_LIFE || '',
    dryRun: false,
  };

  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--dry-run') args.dryRun = true;
    else if (a === '--app-id') args.appId = argv[++i] || '';
    else if (a === '--app-secret') args.appSecret = argv[++i] || '';
    else if (a === '--biz-app-token') args.bizAppToken = argv[++i] || '';
    else if (a === '--biz-table-id') args.bizTableId = argv[++i] || '';
    else if (a === '--life-app-token') args.lifeAppToken = argv[++i] || '';
    else if (a === '--life-table-id') args.lifeTableId = argv[++i] || '';
    else if (a === '--help' || a === '-h') {
      console.log(`Usage:
  FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx \\
  FEISHU_BIZ_APP_TOKEN=bascnxxx FEISHU_BIZ_TABLE_ID=tblxxx \\
  FEISHU_LIFE_APP_TOKEN=bascnxxx FEISHU_LIFE_TABLE_ID=tblxxx \\
  node tools/sync-business-to-life.mjs [--dry-run]`);
      process.exit(0);
    }
  }
  return args;
}

export function round2(n) {
  return Math.round((Number(n) + Number.EPSILON) * 100) / 100;
}

export function textOf(val) {
  if (val == null) return '';
  if (typeof val === 'string') return val.trim();
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  if (Array.isArray(val)) {
    return val
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && typeof item.text === 'string') return item.text;
        return '';
      })
      .join('')
      .trim();
  }
  if (typeof val === 'object' && typeof val.text === 'string') {
    return val.text.trim();
  }
  return '';
}

function arrayOfStrings(val) {
  if (Array.isArray(val)) {
    return val.map((x) => (typeof x === 'string' ? x : x && x.text ? x.text : String(x)));
  }
  if (typeof val === 'string' && val.trim()) return [val.trim()];
  return [];
}

export function timestampToYmUtc8(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n <= 0) return null;
  const d = new Date(n + 8 * 3600 * 1000);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  return `${y}/${m}`;
}

export function normalizeYm(rawMonth, rawTimeMs) {
  const txt = textOf(rawMonth).replace('-', '/');
  const m = txt.match(/^(\d{4})\/(\d{2})$/);
  if (m) return `${m[1]}/${m[2]}`;
  return timestampToYmUtc8(rawTimeMs);
}

export function monthFirstNoonUtc8Ms(ym) {
  const m = String(ym).match(/^(\d{4})\/(\d{2})$/);
  if (!m) throw new Error(`Invalid YYYY/MM month: ${ym}`);
  const year = Number(m[1]);
  const month = Number(m[2]);
  return Date.UTC(year, month - 1, 1, 4, 0, 0, 0);
}

export function buildTargetFields(ym, netAmount) {
  return {
    事件: `${ym} 生意净结余（自动联动）`,
    收支: round2(netAmount),
    标签: '生意结余',
    分类: ['生意结余'],
    渠道: '生意账本自动同步',
    时间: monthFirstNoonUtc8Ms(ym),
  };
}

export function aggregateBusinessRecords(items) {
  const sums = new Map();
  const counts = new Map();
  for (const item of items) {
    const fields = (item && item.fields) || {};
    const ym = normalizeYm(fields['月份'], fields['时间']);
    if (!ym) continue;
    const rawAmt = fields['收支'];
    const amt = typeof rawAmt === 'number' ? rawAmt : Number(textOf(rawAmt));
    if (!Number.isFinite(amt)) continue;
    sums.set(ym, round2((sums.get(ym) || 0) + amt));
    counts.set(ym, (counts.get(ym) || 0) + 1);
  }
  return { sums, counts };
}

export function indexExistingLifeSyncRows(items) {
  const byMonth = new Map();
  for (const item of items) {
    const fields = (item && item.fields) || {};
    const tag = textOf(fields['标签']);
    const ev = textOf(fields['事件']);
    if (tag !== '生意结余') continue;
    const m = ev.match(/^(\d{4}\/\d{2})/);
    const ym = m ? m[1] : normalizeYm(fields['月份'], fields['时间']);
    if (!ym) continue;
    if (!byMonth.has(ym)) {
      byMonth.set(ym, item);
    }
  }
  return byMonth;
}

export function isRecordUpToDate(existingItem, targetFields) {
  if (!existingItem || !existingItem.fields) return false;
  const f = existingItem.fields;
  const ev = textOf(f['事件']);
  const amt = typeof f['收支'] === 'number' ? f['收支'] : Number(textOf(f['收支']));
  const tag = textOf(f['标签']);
  const cats = arrayOfStrings(f['分类']);
  const ch = textOf(f['渠道']);
  const ts = Number(f['时间']);

  if (ev !== targetFields['事件']) return false;
  if (!Number.isFinite(amt) || Math.abs(amt - targetFields['收支']) >= 0.005) return false;
  if (tag !== targetFields['标签']) return false;
  if (!cats.includes('生意结余')) return false;
  if (ch !== targetFields['渠道']) return false;
  if (Number.isFinite(ts) && ts > 0 && ts !== targetFields['时间']) return false;
  return true;
}

async function feishuRequest(apiBase, token, method, apiPath, body) {
  const res = await fetch(`${apiBase}${apiPath}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json; charset=utf-8',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok || data.code !== 0) {
    throw new Error(`Feishu API ${method} ${apiPath} failed: HTTP ${res.status} code=${data.code} msg=${data.msg || 'unknown'}`);
  }
  return data.data;
}

async function getTenantAccessToken(cfg) {
  const res = await fetch(`${cfg.apiBase}/open-apis/auth/v3/tenant_access_token/internal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({
      app_id: cfg.appId,
      app_secret: cfg.appSecret,
    }),
  });
  const data = await res.json();
  if (!res.ok || data.code !== 0 || !data.tenant_access_token) {
    throw new Error(`Feishu auth failed: HTTP ${res.status} code=${data.code} msg=${data.msg || 'unknown'}`);
  }
  return data.tenant_access_token;
}

async function listAllRecords(cfg, token, appToken, tableId) {
  const all = [];
  let pageToken = '';
  while (true) {
    const qs = new URLSearchParams({ page_size: '500' });
    if (pageToken) qs.set('page_token', pageToken);
    const data = await feishuRequest(
      cfg.apiBase,
      token,
      'GET',
      `/open-apis/bitable/v1/apps/${appToken}/tables/${tableId}/records?${qs.toString()}`
    );
    if (Array.isArray(data.items)) {
      all.push(...data.items);
    }
    if (!data.has_more || !data.page_token) break;
    pageToken = data.page_token;
  }
  return all;
}

async function main() {
  const cfg = parseArgs(process.argv);
  if (!cfg.appId || !cfg.appSecret || !cfg.bizAppToken || !cfg.bizTableId || !cfg.lifeAppToken || !cfg.lifeTableId) {
    console.error('Error: Missing required env/flags. Run with --help for usage.');
    process.exit(1);
  }

  const token = await getTenantAccessToken(cfg);
  const bizItems = await listAllRecords(cfg, token, cfg.bizAppToken, cfg.bizTableId);
  const lifeItems = await listAllRecords(cfg, token, cfg.lifeAppToken, cfg.lifeTableId);

  const { sums, counts } = aggregateBusinessRecords(bizItems);
  const existingByMonth = indexExistingLifeSyncRows(lifeItems);
  const months = Array.from(sums.keys()).sort();

  let created = 0;
  let updated = 0;
  let unchanged = 0;
  let grandTotal = 0;

  for (const ym of months) {
    const net = sums.get(ym);
    grandTotal = round2(grandTotal + net);
    const targetFields = buildTargetFields(ym, net);
    const existing = existingByMonth.get(ym);

    if (existing) {
      if (isRecordUpToDate(existing, targetFields)) {
        unchanged++;
        continue;
      }
      if (!cfg.dryRun) {
        await feishuRequest(
          cfg.apiBase,
          token,
          'PUT',
          `/open-apis/bitable/v1/apps/${cfg.lifeAppToken}/tables/${cfg.lifeTableId}/records/${existing.record_id}`,
          { fields: targetFields }
        );
      }
      updated++;
      console.log(`[sync] PUT ${ym} (${existing.record_id}) -> net=${net.toFixed(2)} (records=${counts.get(ym)})`);
    } else {
      if (!cfg.dryRun) {
        const res = await feishuRequest(
          cfg.apiBase,
          token,
          'POST',
          `/open-apis/bitable/v1/apps/${cfg.lifeAppToken}/tables/${cfg.lifeTableId}/records`,
          { fields: targetFields }
        );
        const recId = res && res.record && res.record.record_id ? res.record.record_id : 'new';
        console.log(`[sync] POST ${ym} (${recId}) -> net=${net.toFixed(2)} (records=${counts.get(ym)})`);
      } else {
        console.log(`[sync] DRY-RUN POST ${ym} -> net=${net.toFixed(2)} (records=${counts.get(ym)})`);
      }
      created++;
    }
  }

  console.log(
    `[sync] OK months=${months.length} biz_records=${bizItems.length} total_net=${grandTotal.toFixed(2)} created=${created} updated=${updated} unchanged=${unchanged}${cfg.dryRun ? ' (dry-run)' : ''}`
  );
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    console.error(`[sync] ERROR: ${err.message}`);
    process.exit(1);
  });
}
