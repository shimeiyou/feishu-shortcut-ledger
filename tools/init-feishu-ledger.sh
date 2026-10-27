#!/usr/bin/env bash
# ==============================================================================
# init-lark-cli.sh — 使用飞书官方 CLI (lark-cli base) 一键初始化双账本多维表格、
#                    3 个自动公式列（收入 / 支出 / 月份）及 8 大仪表盘看板组件指南
#
# 适用人群：喜欢在终端使用 `lark-cli`（或结合 `node tools/init-bitable.mjs`）完成建表的用户
# 依赖工具：lark-cli (https://github.com/larksuite/cli) 或 Node.js 18+
#
# 用法：
#   export FEISHU_APP_TOKEN="YOUR_BITABLE_APP_TOKEN"
#   bash tools/init-lark-cli.sh [--dry-run]
# ==============================================================================
set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

APP_TOKEN="${FEISHU_APP_TOKEN:-YOUR_BITABLE_APP_TOKEN}"
TABLE_BIZ_NAME="${FEISHU_TABLE_BIZ_NAME:-副业项目账本}"
TABLE_LIFE_NAME="${FEISHU_TABLE_LIFE_NAME:-日常消费账本}"

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[DRY-RUN] $*"
  else
    echo "[EXEC] $*"
    "$@"
  fi
}

echo "======================================================================"
echo " 飞书多维表格 (Bitable) 双账本结构初始化 — lark-cli base"
echo " App Token : ${APP_TOKEN}"
echo " 账本 1    : ${TABLE_BIZ_NAME}"
echo " 账本 2    : ${TABLE_LIFE_NAME}"
echo "======================================================================"

# ------------------------------------------------------------------------------
# 1. 创建数据表并配置基础写入列 + 3 个自动公式列
# ------------------------------------------------------------------------------
init_table_with_lark_cli() {
  local tbl_name="$1"
  local tbl_id_var="$2"
  local is_life="${3:-0}"
  echo ""
  echo ">>> 正在初始化数据表：${tbl_name}"

  # Step 1.1 创建数据表
  run_cmd lark-cli base table create \
    --app-token "${APP_TOKEN}" \
    --name "${tbl_name}"

  local tbl_id="${!tbl_id_var:-YOUR_TABLE_ID}"

  # Step 1.2 基础字段（由 iPhone 快捷指令 / REST API 直接写入）
  run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
    --json '{"field_name":"收支","type":2,"property":{"formatter":"0.00"}}'

  run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
    --json '{"field_name":"标签","type":1}'

  run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
    --json '{"field_name":"分类","type":4,"property":{"options":[{"name":"餐饮"},{"name":"交通"},{"name":"购物"},{"name":"居住水电"},{"name":"娱乐休闲"},{"name":"医疗健康"},{"name":"主业收入"},{"name":"副业收入"},{"name":"采购成本"},{"name":"运营支出"},{"name":"设备工具"},{"name":"生意结余"},{"name":"其他"}]}}'

  run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
    --json '{"field_name":"时间","type":5,"property":{"date_formatter":"yyyy/MM/dd","auto_fill":true}}'

  run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
    --json '{"field_name":"渠道","type":1}'

  # Step 1.3 三个核心自动计算公式列（供仪表盘 8 大图表聚合统计；生活账本支持「生意结余」按月自动联动）
  if [[ "$is_life" == "1" ]]; then
    run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
      --json '{"field_name":"收入","type":20,"property":{"formula_expression":"IF([标签]=\"生意结余\",[收支],IF([收支]>0,[收支],0))","formatter":"0.00"}}'

    run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
      --json '{"field_name":"支出","type":20,"property":{"formula_expression":"IF([标签]=\"生意结余\",0,IF([收支]<0,ABS([收支]),0))","formatter":"0.00"}}'
  else
    run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
      --json '{"field_name":"收入","type":20,"property":{"formula_expression":"IF([收支]>0,[收支],0)","formatter":"0.00"}}'

    run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
      --json '{"field_name":"支出","type":20,"property":{"formula_expression":"IF([收支]<0,ABS([收支]),0)","formatter":"0.00"}}'
  fi

  run_cmd lark-cli base field create --app-token "${APP_TOKEN}" --table-id "${tbl_id}" \
    --json '{"field_name":"月份","type":20,"property":{"formula_expression":"TODATE([时间],\"YYYY/MM\")"}}'
}

if ! command -v lark-cli >/dev/null 2>&1 && [[ "$DRY_RUN" == "0" ]]; then
  echo "[提示] 当前环境未检测到 lark-cli，自动切换为 dry-run 预览模式（也可直接运行：node tools/init-bitable.mjs）"
  DRY_RUN=1
fi

init_table_with_lark_cli "${TABLE_BIZ_NAME}" "FEISHU_TABLE_ID_BIZ" 0
init_table_with_lark_cli "${TABLE_LIFE_NAME}" "FEISHU_TABLE_ID_LIFE" 1

# ------------------------------------------------------------------------------
# 2. 飞书多维表格「仪表盘（Dashboard）」8 大核心看板组件配置规范
# ------------------------------------------------------------------------------
cat <<'DASHBOARD'

======================================================================
 飞书多维表格「收支仪表盘」8 大可视化组件标准配置清单
 （在多维表格左侧栏点击「+ 新建仪表盘」，按以下参数依次添加 8 个图表组件）
======================================================================

  [组件 1] 总收入（统计数字卡 / 数字指标卡）
    - 数据源  ：选择对应数据表（日常消费账本 / 副业项目账本）
    - 统计方式：汇总值 -> 字段选择「收入」 -> 求和 (SUM)
    - 样式建议：前缀 "¥"，保留 2 位小数，配色选绿色或蓝色

  [组件 2] 总支出（统计数字卡 / 数字指标卡）
    - 数据源  ：对应数据表
    - 统计方式：汇总值 -> 字段选择「支出」 -> 求和 (SUM)
    - 样式建议：前缀 "¥"，保留 2 位小数，配色选橙色或红色

  [组件 3] 净结余（统计数字卡 / 数字指标卡）
    - 数据源  ：对应数据表
    - 统计方式：汇总值 -> 字段选择「收支」 -> 求和 (SUM)
    - 说明    ：因「收支」列正数为收入、负数为支出，直接求和即为实时净结余！

  [组件 4] 记账笔数（统计数字卡 / 数字指标卡）
    - 数据源  ：对应数据表
    - 统计方式：记录总数 (COUNT)
    - 样式建议：后缀 "笔"

  [组件 5] 月度收支三柱对比（柱状图 / 分组柱状图）
    - 横轴 (X)：选择公式字段「月份」（按升序排列）
    - 纵轴 (Y)：添加 3 个数值指标（并列分组柱状图）：
                1) 「收入」求和 (SUM)
                2) 「支出」求和 (SUM)
                3) 「收支」求和 (SUM，即当月净结余)

  [组件 6] 月度横向条形图（条形图）
    - 纵轴维度：选择公式字段「月份」
    - 横轴数值：选择「收入」求和 与 「支出」求和（直观对比各月收支体量）

  [组件 7] 各分类支出占比（饼图 / 环形图）
    - 分类维度：选择「标签」（或「分类」）
    - 数值指标：选择公式字段「支出」 -> 求和 (SUM)
    - 筛选条件：可添加过滤条件 `支出 > 0`（自动排除纯收入记录，仅展示各项消费结构占比）

  [组件 8] 每月净结余趋势（折线图 / 面积折线图）
    - 横轴 (X)：选择公式字段「月份」（按时间升序）
    - 纵轴 (Y)：选择「收支」 -> 求和 (SUM)
    - 样式建议：开启平滑曲线与数据标签，一眼看清每月净现金流走势

======================================================================
DASHBOARD
