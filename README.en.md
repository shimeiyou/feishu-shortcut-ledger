# Feishu unified ledger + iPhone screenshot bookkeeping

[中文](README.md) · [MIT](LICENSE)

Screenshot → on-device OCR → **edit the amount** → choose direction/category → write directly to your own Feishu Bitable.

This is a reusable template with no author's credentials, table IDs or server dependency. You need an iPhone and your own Feishu account/application. The v2 template targets mainland Feishu (`open.feishu.cn`), CNY and Asia/Shanghai. International Lark requires separate endpoint/authorization adaptation. Field names remain Chinese and must match the schema.

## Choose your features

| Feature | Required? | Runs on |
| --- | --- | --- |
| OCR, editable amount, categories, checked Feishu write | Yes | iPhone + Feishu |
| Monthly business-to-life net transfer | Optional | Your Apps Script project, once daily |
| Google Sheets backup | **Optional, disabled by default** | Separate module in that project |

Google is not required for recording transactions. Formula columns update in Feishu. Monthly transfer **rows** require the separate scheduled reconciler; the Shortcut does not update them.

## Setup

1. Create your own Feishu internal app and grant it edit access to your Base: [application setup](docs/02-feishu-open-app-setup.md).
2. Create the single v2 table: [schema](docs/01-feishu-bitable-setup.md). With Node.js 18+, `node tools/init-bitable.mjs --dry-run` previews it. Set `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_APP_TOKEN` privately, then run with `--apply` to create a new table. Existing same-name tables are never changed. Samples require `--insert-sample`.
3. Download [the signed public template](shortcuts/飞书一体账本-通用版.shortcut), open it in Shortcuts and enter your App ID, App Secret and the **one** record endpoint: `https://open.feishu.cn/open-apis/bitable/v1/apps/YOUR_BITABLE_APP_TOKEN/tables/YOUR_TABLE_ID/records`.
4. Test all four branches, amount edits and failure handling with small test entries before enabling Back Tap. See [iPhone guide](docs/03-iphone-shortcut-guide.md).
5. Optional: [daily cloud reconciliation](docs/05-cloud-daily-sync.md), then [optional Sheets backup](docs/06-optional-google-sheets.md). No public Web App deployment or always-on personal computer is required.

The current signed artifact has an [auditable XML source](shortcuts/Feishu-Unified-Ledger-Unsigned.shortcut) and [signing receipt](shortcuts/signing-receipt.json). Signing does not establish iPhone compatibility; this generalized build still needs device/deployment acceptance testing.

## Behavior and accounting

One table uses `账本=生意` for business/projects and `账本=生活` for personal transactions. Amounts are positive for income and negative for expenses. Common expenses save after one category choice; other expenses and income ask for a specific note. Native JSON handles quotes/newlines. Success is shown only after Feishu returns `code=0` and `record_id`. An uncertain POST is never automatically repeated; check the table first.

The optional reconciler computes in integer cents, reads all pages, detects concurrent changes and duplicate automatic rows, and verifies each derived write. It does not delete raw transactions. Default execution is daily near **03:30 Asia/Shanghai**, with roughly ±15 minutes variation. Newly entered transactions can wait until the next successful run for the derived monthly transfer.

**Exclude `来源=自动联动` from cross-ledger totals and transaction counts.** Otherwise the business detail and its monthly transfer are double-counted. Personal disposable balance includes the derived transfer; a business loss reduces personal income rather than creating personal consumption. Sheets is a one-way mirror, never the authority for rewriting Feishu.

## Build and tests

Python 3.10+ and Node.js 18+, no third-party packages:

```bash
python3 tools/build-shortcut.py
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/cloud.cjs
node tests/init.mjs
python3 tools/check-public.py
```

Copy the example config to `config/shortcut-config.local.json` to customize categories and `ask_note`. Write customized artifacts to ignored `shortcuts/private/`. On Mac, `--sign` uses Apple's local `shortcuts sign`; it never uploads credentials. Read the [migration guide](docs/07-migration-v1-to-v2.md) before upgrading v1's separate tables. Historical v1 material under `legacy/v1/` is not the installation path.

Secrets belong only on your phone, in private environment variables, or private Script Properties (readable by project editors). Do not publish configured shortcuts, private configs, exports or real records. Offline tests simulate action graphs, initialization and failure paths; they do not claim device or new-account API acceptance.
