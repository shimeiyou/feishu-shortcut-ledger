# Feishu Bitable + iPhone Shortcuts Auto-Bookkeeping (`feishu-shortcut-ledger`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**[中文保姆级教程 (README.md)](README.md)**

A zero-middleware open-source toolkit and beginner tutorial for **automated personal & side-business bookkeeping** using **iPhone Shortcuts (iOS native OCR)** and **Feishu Bitable (Lark Base) Open API (`bitable/v1`)**.

---

## Architecture & Highlights

1. **Zero Middleware & 100% Privacy**:
   - Uses iOS on-device OCR (`extracttextfromimage`) and regex (`[0-9]+\.[0-9]{1,3}`) to extract payment amounts from screenshots in memory without saving screenshots to your photo library or uploading images anywhere.
   - Talks directly to the official Feishu Open Platform REST API (`POST /open-apis/auth/v3/tenant_access_token/internal` and `POST /open-apis/bitable/v1/apps/:app_token/tables/:table_id/records`).
2. **Signed-Amount Field + 3 Formula Columns + 8 Dashboard Widgets**:
   - **6 Base Fields** written by the Shortcut / API:
     - `事件` (Text, Primary): Event / summary note
     - `收支` (Number, `0.00`): **Positive for income (e.g. `500`), negative for expense (e.g. `-35.5`)**
     - `标签` (Text): Category tag string
     - `分类` (Multi/Single Select): Category options (`餐饮`, `交通`, `购物`, `主业收入`, `副业收入`, `采购成本`, etc.)
     - `时间` (Date, `yyyy/MM/dd`, auto-fill creation time)
     - `渠道` (Text, optional): Payment channel (`微信支付` / `支付宝` / `银行卡` / `现金`)
   - **3 Auto-Calculated Formula Fields**:
     - `收入` (Formula): `IF([收支]>0,[收支],0)`
     - `支出` (Formula): `IF([收支]<0,ABS([收支]),0)`
     - `月份` (Formula): `TEXT([时间],"YYYY/MM")`
   - **8 Dashboard Widgets**:
     1. Total Income (`总收入`, Stat Card: `SUM(收入)`)
     2. Total Expense (`总支出`, Stat Card: `SUM(支出)`)
     3. Net Balance (`净结余`, Stat Card: `SUM(收支)`)
     4. Transaction Count (`记账笔数`, Stat Card: `COUNT(*)`)
     5. Monthly 3-Bar Comparison (`月度收支三柱对比`, Bar Chart: X=`月份`, Y=`收入` / `支出` / `收支`)
     6. Monthly Horizontal Bar (`月度横向条形图`, Horizontal Bar Chart by `月份`)
     7. Expense Breakdown by Category (`各分类支出占比`, Pie/Donut Chart: Category=`标签`/`分类`, Value=`SUM(支出)`)
     8. Monthly Net Cashflow Trend (`每月净结余趋势`, Line Chart: X=`月份`, Y=`SUM(收支)`)
3. **One-Click CLI Initializers & Programmatic Shortcut Compiler**:
   - `tools/init-bitable.mjs`: Zero-dependency Node.js 18+ script using native `fetch` to create the dual-ledger tables, formula columns, and sample records.
   - `init-feishu-ledger.sh` (`tools/init-lark-cli.sh`): Automation script for `lark-cli base` + 8 Dashboard widget specification.
   - `tools/build-shortcut.py`: Pure Python 3 script that compiles `config/shortcut-config.example.json` into both an auditable unsigned XML plist shortcut (`shortcuts/Feishu-Dual-Ledger-Unsigned.shortcut`) and a signed, ready-to-import iOS shortcut (`shortcuts/飞书双账本自动记账-通用模板.shortcut`).

---

## Quick Start

```bash
# 1. Preview Feishu Bitable API schema creation payloads (Dry Run)
node tools/init-bitable.mjs --dry-run

# 2. Initialize tables & 3 formula columns in your Feishu Bitable
FEISHU_APP_ID="YOUR_FEISHU_APP_ID" \
FEISHU_APP_SECRET="YOUR_FEISHU_APP_SECRET" \
FEISHU_APP_TOKEN="YOUR_BITABLE_APP_TOKEN" \
node tools/init-bitable.mjs --insert-sample

# 3. Or initialize via official lark-cli
FEISHU_APP_TOKEN="YOUR_BITABLE_APP_TOKEN" bash init-feishu-ledger.sh

# 4. Customize categories and rebuild the .shortcut files
python3 tools/build-shortcut.py --config config/shortcut-config.example.json --sign
```

---

## Acknowledgments

We gratefully acknowledge the Chinese efficiency and iOS Shortcuts community (such as SSPai 少数派 contributors) for sharing ideas around combining mobile screenshot OCR with cloud spreadsheets for personal bookkeeping.

---

## License

Released under the [MIT License](LICENSE).
