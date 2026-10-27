#!/usr/bin/env python3
"""
build-shortcut.py — Clean-room iOS Shortcut (.shortcut) generator for Feishu Bitable Dual-Ledger Auto-Bookkeeping.

Zero third-party Python dependencies (uses standard library `plistlib`, `json`, `uuid`, `urllib.request`).
Reads a JSON configuration file (default: `config/shortcut-config.example.json`), generates:
  1. An auditable unsigned XML plist shortcut (`shortcuts/Feishu-Dual-Ledger-Unsigned.shortcut`)
  2. Optionally (`--sign`), an Apple-signed `.shortcut` (`shortcuts/飞书双账本自动记账-通用模板.shortcut`)
     that can be directly imported on iPhone / iPad / macOS.

Usage:
  python3 tools/build-shortcut.py
  python3 tools/build-shortcut.py --config config/shortcut-config.example.json --sign
"""

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "shortcut-config.example.json"
UNSIGNED_OUT = ROOT / "shortcuts" / "Feishu-Dual-Ledger-Unsigned.shortcut"
SIGNED_OUT = ROOT / "shortcuts" / "飞书双账本自动记账-通用模板.shortcut"


def uid() -> str:
    return str(uuid.uuid4()).upper()


def var_token(name: str) -> dict:
    return {"Type": "Variable", "VariableName": name}


def out_token(output_name: str, output_uuid: str) -> dict:
    return {"Type": "ActionOutput", "OutputName": output_name, "OutputUUID": output_uuid}


def var_attach(name: str) -> dict:
    return {
        "Value": var_token(name),
        "WFSerializationType": "WFTextTokenAttachment",
    }


def out_attach(output_name: str, output_uuid: str) -> dict:
    return {
        "Value": out_token(output_name, output_uuid),
        "WFSerializationType": "WFTextTokenAttachment",
    }


def token_str(*parts) -> dict:
    s = ""
    attachments = {}
    for p in parts:
        if isinstance(p, str):
            s += p
        elif isinstance(p, dict):
            pos = len(s)
            s += "\ufffc"
            attachments[f"{{{pos}, 1}}"] = p
        else:
            raise ValueError(f"Unsupported token part: {p!r}")
    return {
        "Value": {
            "string": s,
            "attachmentsByRange": attachments,
        },
        "WFSerializationType": "WFTextTokenString",
    }


def act_text(text_val, u=None):
    u = u or uid()
    return u, {
        "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
        "WFWorkflowActionParameters": {
            "UUID": u,
            "WFTextActionText": text_val,
        },
    }


def act_setvar(var_name: str, input_attach: dict) -> dict:
    return {
        "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
        "WFWorkflowActionParameters": {
            "WFVariableName": var_name,
            "WFInput": input_attach,
        },
    }


def set_text_var(actions: list, var_name: str, text_val) -> str:
    u, a = act_text(text_val)
    actions.append(a)
    actions.append(act_setvar(var_name, out_attach("文本", u)))
    return u


def build_shortcut_dict(cfg: dict) -> dict:
    actions = []
    feishu = cfg["feishu"]
    ledgers = cfg["ledgers"]
    menu_top = cfg["menu_top"]
    cats = cfg["categories"]

    # 0. Setup Comment + 4 Configurable Parameters (Import Questions)
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
        "WFWorkflowActionParameters": {
            "WFCommentActionText": (
                "【飞书多维表格 + iPhone 快捷指令自动记账（通用双账本模板）】\n"
                "首次导入或使用时，请在下方 4 个「文本」动作框中填入你自己的飞书配置：\n"
                "1. app_id：飞书开放平台企业自建应用的 App ID（如 cli_xxxxxxxxxxxxxxxx）\n"
                "2. app_secret：飞书应用的 32 位 App Secret\n"
                "3. biz_url：副业/项目账本（或主表）新增记录 API 地址\n"
                "4. life_url：日常消费账本新增记录 API 地址（若单表记账可填同一地址）\n"
                "详细图文教程见开源仓库 README.md。"
            )
        },
    })

    # ActionIndex 1 & 2: app_id
    set_text_var(actions, "app_id", feishu.get("app_id", "YOUR_FEISHU_APP_ID"))
    # ActionIndex 3 & 4: app_secret
    set_text_var(actions, "app_secret", feishu.get("app_secret", "YOUR_FEISHU_APP_SECRET"))
    # ActionIndex 5 & 6: biz_url
    set_text_var(
        actions,
        "biz_url",
        feishu.get(
            "biz_record_url",
            "https://open.feishu.cn/open-apis/bitable/v1/apps/YOUR_BITABLE_APP_TOKEN_BIZ/tables/YOUR_TABLE_ID_BIZ/records",
        ),
    )
    # ActionIndex 7 & 8: life_url
    set_text_var(
        actions,
        "life_url",
        feishu.get(
            "life_record_url",
            "https://open.feishu.cn/open-apis/bitable/v1/apps/YOUR_BITABLE_APP_TOKEN_LIFE/tables/YOUR_TABLE_ID_LIFE/records",
        ),
    )

    # 1. Screenshot -> OCR -> Regex Match Amount -> Variable `money`
    u_shot = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.takescreenshot",
        "WFWorkflowActionParameters": {"UUID": u_shot},
    })
    u_ocr = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.extracttextfromimage",
        "WFWorkflowActionParameters": {
            "UUID": u_ocr,
            "WFImage": out_attach("截屏", u_shot),
        },
    })
    u_match = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.text.match",
        "WFWorkflowActionParameters": {
            "UUID": u_match,
            "WFMatchTextPattern": r"[0-9]+\.[0-9]{1,3}",
            "text": token_str(out_token("图像中的文本", u_ocr)),
        },
    })
    u_count = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.count",
        "WFWorkflowActionParameters": {
            "UUID": u_count,
            "Input": out_attach("匹配", u_match),
        },
    })

    # If matched count == 0 -> Ask user for amount manually
    g_if0 = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_if0,
            "WFCondition": 4,
            "WFControlFlowMode": 0,
            "WFInput": {
                "Type": "Variable",
                "Variable": out_attach("数量", u_count),
            },
            "WFNumberValue": "0",
        },
    })
    u_ask_money = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
        "WFWorkflowActionParameters": {
            "UUID": u_ask_money,
            "WFAskActionPrompt": "未在截图中识别到带小数点的金额，请手动输入金额：",
            "WFInputType": "Number",
        },
    })
    actions.append(act_setvar("money", out_attach("提供的输入", u_ask_money)))

    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_if0,
            "WFControlFlowMode": 1,
        },
    })

    # Else if matched count > 1 -> Let user pick which number is the real amount
    g_if1 = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_if1,
            "WFCondition": 2,
            "WFControlFlowMode": 0,
            "WFInput": {
                "Type": "Variable",
                "Variable": out_attach("数量", u_count),
            },
            "WFNumberValue": "1",
        },
    })
    u_choose_money = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefromlist",
        "WFWorkflowActionParameters": {
            "UUID": u_choose_money,
            "WFChooseFromListActionPrompt": "识别到多个金额，请点选本次记账金额：",
            "WFInput": out_attach("匹配", u_match),
        },
    })
    actions.append(act_setvar("money", out_attach("选取的项目", u_choose_money)))

    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_if1,
            "WFControlFlowMode": 1,
        },
    })
    actions.append(act_setvar("money", out_attach("匹配", u_match)))
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_if1,
            "WFControlFlowMode": 2,
        },
    })
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_if0,
            "UUID": uid(),
            "WFControlFlowMode": 2,
        },
    })

    # 2. Top-level 4-Way Ledger & Direction Menu
    g_top = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_top,
            "WFControlFlowMode": 0,
            "WFMenuItems": menu_top,
            "WFMenuPrompt": token_str("记账 ¥", var_token("money"), " 元，请选择账本与收支类型："),
        },
    })

    # --- Branch 1: 副业项目收入 (Positive 收支) ---
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_top,
            "WFControlFlowMode": 1,
            "WFMenuItemTitle": menu_top[0],
        },
    })
    actions.append(act_setvar("record_url", var_attach("biz_url")))
    set_text_var(actions, "账本", ledgers["biz_name"])
    set_text_var(actions, "收支类型", "收入")
    actions.append(act_setvar("金额", var_attach("money")))
    u_list_biz_inc = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.list",
        "WFWorkflowActionParameters": {
            "UUID": u_list_biz_inc,
            "WFItems": cats["biz_income_options"],
        },
    })
    u_choose_biz_inc = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefromlist",
        "WFWorkflowActionParameters": {
            "UUID": u_choose_biz_inc,
            "WFChooseFromListActionPrompt": token_str(menu_top[0], " +¥", var_token("money"), "，请选择分类："),
            "WFInput": out_attach("列表", u_list_biz_inc),
        },
    })
    actions.append(act_setvar("分类", out_attach("选取的项目", u_choose_biz_inc)))
    u_ask_biz_inc = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
        "WFWorkflowActionParameters": {
            "UUID": u_ask_biz_inc,
            "WFAskActionPrompt": "请输入事件/摘要（可直接回车使用分类名）：",
            "WFAskActionDefaultAnswer": token_str(var_token("分类")),
        },
    })
    actions.append(act_setvar("event", out_attach("提供的输入", u_ask_biz_inc)))
    set_text_var(
        actions,
        "notify_msg",
        token_str("已记入", ledgers["biz_name"], "：", var_token("分类"), " +¥", var_token("money"), "（", var_token("event"), "）"),
    )

    # --- Branch 2: 副业项目支出 (Negative 收支 = money * -1) ---
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_top,
            "WFControlFlowMode": 1,
            "WFMenuItemTitle": menu_top[1],
        },
    })
    actions.append(act_setvar("record_url", var_attach("biz_url")))
    set_text_var(actions, "账本", ledgers["biz_name"])
    set_text_var(actions, "收支类型", "支出")
    u_math_biz = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.math",
        "WFWorkflowActionParameters": {
            "UUID": u_math_biz,
            "WFInput": var_attach("money"),
            "WFMathOperand": "-1",
            "WFMathOperation": "×",
        },
    })
    actions.append(act_setvar("金额", out_attach("计算结果", u_math_biz)))

    biz_quick = cats["biz_expense_quick"]
    g_biz = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_biz,
            "WFControlFlowMode": 0,
            "WFMenuItems": [x["title"] for x in biz_quick],
            "WFMenuPrompt": token_str(menu_top[1], " -¥", var_token("money"), "，请选择分类："),
        },
    })

    for item in biz_quick:
        title = item["title"]
        cat = item["category"]
        note = item["default_note"]
        actions.append({
            "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": g_biz,
                "WFControlFlowMode": 1,
                "WFMenuItemTitle": title,
            },
        })
        if cat is not None and note is not None:
            set_text_var(actions, "分类", cat)
            set_text_var(actions, "event", note)
        elif cat is not None and note is None:
            set_text_var(actions, "分类", cat)
            u_ask_dev = uid()
            actions.append({
                "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
                "WFWorkflowActionParameters": {
                    "UUID": u_ask_dev,
                    "WFAskActionPrompt": f"请输入{cat}名称/备注：",
                    "WFAskActionDefaultAnswer": cat,
                },
            })
            actions.append(act_setvar("event", out_attach("提供的输入", u_ask_dev)))
        else:
            u_list_biz = uid()
            actions.append({
                "WFWorkflowActionIdentifier": "is.workflow.actions.list",
                "WFWorkflowActionParameters": {
                    "UUID": u_list_biz,
                    "WFItems": cats["biz_expense_list"],
                },
            })
            u_choose_biz = uid()
            actions.append({
                "WFWorkflowActionIdentifier": "is.workflow.actions.choosefromlist",
                "WFWorkflowActionParameters": {
                    "UUID": u_choose_biz,
                    "WFChooseFromListActionPrompt": "请选择项目支出分类：",
                    "WFInput": out_attach("列表", u_list_biz),
                },
            })
            actions.append(act_setvar("分类", out_attach("选取的项目", u_choose_biz)))
            u_ask_other_biz = uid()
            actions.append({
                "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
                "WFWorkflowActionParameters": {
                    "UUID": u_ask_other_biz,
                    "WFAskActionPrompt": "请输入事件备注：",
                    "WFAskActionDefaultAnswer": token_str(var_token("分类")),
                },
            })
            actions.append(act_setvar("event", out_attach("提供的输入", u_ask_other_biz)))

    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_biz,
            "UUID": uid(),
            "WFControlFlowMode": 2,
        },
    })
    set_text_var(
        actions,
        "notify_msg",
        token_str("已记入", ledgers["biz_name"], "：", var_token("分类"), " -¥", var_token("money"), "（", var_token("event"), "）"),
    )

    # --- Branch 3: 日常消费支出 (Negative 收支 = money * -1) ---
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_top,
            "WFControlFlowMode": 1,
            "WFMenuItemTitle": menu_top[2],
        },
    })
    actions.append(act_setvar("record_url", var_attach("life_url")))
    set_text_var(actions, "账本", ledgers["life_name"])
    set_text_var(actions, "收支类型", "支出")
    u_math_life = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.math",
        "WFWorkflowActionParameters": {
            "UUID": u_math_life,
            "WFInput": var_attach("money"),
            "WFMathOperand": "-1",
            "WFMathOperation": "×",
        },
    })
    actions.append(act_setvar("金额", out_attach("计算结果", u_math_life)))
    u_list_life_exp = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.list",
        "WFWorkflowActionParameters": {
            "UUID": u_list_life_exp,
            "WFItems": cats["life_expense_list"],
        },
    })
    u_choose_life_exp = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefromlist",
        "WFWorkflowActionParameters": {
            "UUID": u_choose_life_exp,
            "WFChooseFromListActionPrompt": token_str(menu_top[2], " -¥", var_token("money"), "，请选择分类："),
            "WFInput": out_attach("列表", u_list_life_exp),
        },
    })
    actions.append(act_setvar("分类", out_attach("选取的项目", u_choose_life_exp)))
    u_ask_life_exp = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
        "WFWorkflowActionParameters": {
            "UUID": u_ask_life_exp,
            "WFAskActionPrompt": "备注（可直接回车默认使用分类名）：",
            "WFAskActionDefaultAnswer": token_str(var_token("分类")),
        },
    })
    actions.append(act_setvar("event", out_attach("提供的输入", u_ask_life_exp)))
    set_text_var(
        actions,
        "notify_msg",
        token_str("已记入", ledgers["life_name"], "：", var_token("分类"), " -¥", var_token("money"), "（", var_token("event"), "）"),
    )

    # --- Branch 4: 日常其他收入 (Positive 收支) ---
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_top,
            "WFControlFlowMode": 1,
            "WFMenuItemTitle": menu_top[3],
        },
    })
    actions.append(act_setvar("record_url", var_attach("life_url")))
    set_text_var(actions, "账本", ledgers["life_name"])
    set_text_var(actions, "收支类型", "收入")
    actions.append(act_setvar("金额", var_attach("money")))
    u_list_life_inc = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.list",
        "WFWorkflowActionParameters": {
            "UUID": u_list_life_inc,
            "WFItems": cats["life_income_list"],
        },
    })
    u_choose_life_inc = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefromlist",
        "WFWorkflowActionParameters": {
            "UUID": u_choose_life_inc,
            "WFChooseFromListActionPrompt": token_str(menu_top[3], " +¥", var_token("money"), "，请选择分类："),
            "WFInput": out_attach("列表", u_list_life_inc),
        },
    })
    actions.append(act_setvar("分类", out_attach("选取的项目", u_choose_life_inc)))
    u_ask_life_inc = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
        "WFWorkflowActionParameters": {
            "UUID": u_ask_life_inc,
            "WFAskActionPrompt": "备注（可直接回车默认使用分类名）：",
            "WFAskActionDefaultAnswer": token_str(var_token("分类")),
        },
    })
    actions.append(act_setvar("event", out_attach("提供的输入", u_ask_life_inc)))
    set_text_var(
        actions,
        "notify_msg",
        token_str("已记入", ledgers["life_name"], "：", var_token("分类"), " +¥", var_token("money"), "（", var_token("event"), "）"),
    )

    # End Top Menu
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.choosefrommenu",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_top,
            "UUID": uid(),
            "WFControlFlowMode": 2,
        },
    })

    # 3. Call Feishu Open Platform Official REST API
    # 3.1 Get tenant_access_token
    u_tok_req = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "ShowHeaders": False,
            "UUID": u_tok_req,
            "WFHTTPMethod": "POST",
            "WFJSONValues": {
                "Value": {
                    "WFDictionaryFieldValueItems": [
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "app_id"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": token_str(var_token("app_id")),
                        },
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "app_secret"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": token_str(var_token("app_secret")),
                        },
                    ]
                },
                "WFSerializationType": "WFDictionaryFieldValue",
            },
            "WFURL": "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        },
    })
    u_tok_val = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
        "WFWorkflowActionParameters": {
            "UUID": u_tok_val,
            "WFDictionaryKey": "tenant_access_token",
            "WFGetDictionaryValueType": "Value",
            "WFInput": out_attach("URL 的内容", u_tok_req),
        },
    })
    actions.append(act_setvar("feishu_token", out_attach("词典值", u_tok_val)))

    # 3.2 Build JSON request body matching our Bitable schema:
    # Base fields: 事件 (Text), 收支 (Number: +income / -expense), 标签 (Text), 分类 (Multi/Single select)
    set_text_var(
        actions,
        "req_body",
        token_str(
            '{"fields":{"事件":"', var_token("event"),
            '","收支":', var_token("金额"),
            ',"标签":"', var_token("分类"),
            '","分类":["', var_token("分类"), '"]}}'
        ),
    )

    # 3.3 POST record to Feishu Bitable API
    u_rec_req = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "ShowHeaders": True,
            "UUID": u_rec_req,
            "WFHTTPBodyType": "File",
            "WFHTTPHeaders": {
                "Value": {
                    "WFDictionaryFieldValueItems": [
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "Authorization"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": token_str("Bearer ", var_token("feishu_token")),
                        },
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "Content-Type"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": {"Value": {"string": "application/json"}, "WFSerializationType": "WFTextTokenString"},
                        },
                    ]
                },
                "WFSerializationType": "WFDictionaryFieldValue",
            },
            "WFHTTPMethod": "POST",
            "WFRequestVariable": var_attach("req_body"),
            "WFURL": token_str(var_token("record_url")),
        },
    })

    # 3.4 Plan A Auto-Sync: When writing to Business Ledger (账本 == ledgers["biz_name"]),
    #     aggregate current month SUM(收支) from biz_url and upsert into life_url
    g_sync_biz = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_sync_biz,
            "WFControlFlowMode": 0,
            "WFCondition": 4,
            "WFConditionalActionString": ledgers["biz_name"],
            "WFInput": {
                "Type": "Variable",
                "Variable": var_attach("账本"),
            },
        },
    })

    u_fmt_month = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.format.date",
        "WFWorkflowActionParameters": {
            "UUID": u_fmt_month,
            "WFDate": {
                "Value": {"Type": "CurrentDate"},
                "WFSerializationType": "WFTextTokenAttachment",
            },
            "WFDateFormatStyle": "Custom",
            "WFDateFormat": "yyyy/MM",
        },
    })
    actions.append(act_setvar("cur_month", out_attach("格式化后的日期", u_fmt_month)))

    set_text_var(
        actions,
        "sync_event",
        token_str(var_token("cur_month"), " 生意净结余（自动联动）"),
    )

    u_biz_month_req = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "ShowHeaders": True,
            "UUID": u_biz_month_req,
            "WFHTTPHeaders": {
                "Value": {
                    "WFDictionaryFieldValueItems": [
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "Authorization"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": token_str("Bearer ", var_token("feishu_token")),
                        },
                    ]
                },
                "WFSerializationType": "WFDictionaryFieldValue",
            },
            "WFHTTPMethod": "GET",
            "WFURL": token_str(
                var_token("biz_url"),
                "?page_size=500&filter=CurrentValue.%5B%E6%9C%88%E4%BB%BD%5D%3D%22",
                var_token("cur_month"),
                "%22",
            ),
        },
    })

    u_biz_data = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
        "WFWorkflowActionParameters": {
            "UUID": u_biz_data,
            "WFDictionaryKey": "data",
            "WFGetDictionaryValueType": "Value",
            "WFInput": out_attach("URL 的内容", u_biz_month_req),
        },
    })
    u_biz_items = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
        "WFWorkflowActionParameters": {
            "UUID": u_biz_items,
            "WFDictionaryKey": "items",
            "WFGetDictionaryValueType": "Value",
            "WFInput": out_attach("词典值", u_biz_data),
        },
    })

    g_rep = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.repeat.each",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_rep,
            "WFControlFlowMode": 0,
            "WFInput": out_attach("词典值", u_biz_items),
        },
    })
    u_item_fields = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
        "WFWorkflowActionParameters": {
            "UUID": u_item_fields,
            "WFDictionaryKey": "fields",
            "WFGetDictionaryValueType": "Value",
            "WFInput": var_attach("Repeat Item"),
        },
    })
    u_item_amt = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
        "WFWorkflowActionParameters": {
            "UUID": u_item_amt,
            "WFDictionaryKey": "收支",
            "WFGetDictionaryValueType": "Value",
            "WFInput": out_attach("词典值", u_item_fields),
        },
    })
    u_rep_end = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.repeat.each",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_rep,
            "UUID": u_rep_end,
            "WFControlFlowMode": 2,
        },
    })

    u_sum = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.statistics",
        "WFWorkflowActionParameters": {
            "UUID": u_sum,
            "WFInput": out_attach("重复结果", u_rep_end),
            "WFStatisticsOperation": "Sum",
        },
    })
    u_round = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.round",
        "WFWorkflowActionParameters": {
            "UUID": u_round,
            "WFInput": out_attach("总和", u_sum),
            "WFRoundMode": "Normal",
            "WFRoundType": "Hundredths",
        },
    })
    actions.append(act_setvar("month_net", out_attach("四舍五入后的数字", u_round)))

    set_text_var(
        actions,
        "sync_body",
        token_str(
            '{"fields":{"事件":"', var_token("sync_event"),
            '","收支":', var_token("month_net"),
            ',"标签":"生意结余","分类":["生意结余"],"渠道":"生意账本自动同步"}}'
        ),
    )

    u_life_search = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "ShowHeaders": True,
            "UUID": u_life_search,
            "WFHTTPHeaders": {
                "Value": {
                    "WFDictionaryFieldValueItems": [
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "Authorization"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": token_str("Bearer ", var_token("feishu_token")),
                        },
                    ]
                },
                "WFSerializationType": "WFDictionaryFieldValue",
            },
            "WFHTTPMethod": "GET",
            "WFURL": token_str(
                var_token("life_url"),
                "?page_size=20&filter=AND(CurrentValue.%5B%E6%A0%87%E7%AD%BE%5D%3D%22%E7%94%9F%E6%84%8F%E7%BB%93%E4%BD%99%22%2CCurrentValue.%5B%E6%9C%88%E4%BB%BD%5D%3D%22",
                var_token("cur_month"),
                "%22)",
            ),
        },
    })

    u_life_data = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
        "WFWorkflowActionParameters": {
            "UUID": u_life_data,
            "WFDictionaryKey": "data",
            "WFGetDictionaryValueType": "Value",
            "WFInput": out_attach("URL 的内容", u_life_search),
        },
    })
    u_life_total = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
        "WFWorkflowActionParameters": {
            "UUID": u_life_total,
            "WFDictionaryKey": "total",
            "WFGetDictionaryValueType": "Value",
            "WFInput": out_attach("词典值", u_life_data),
        },
    })
    u_life_items = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
        "WFWorkflowActionParameters": {
            "UUID": u_life_items,
            "WFDictionaryKey": "items",
            "WFGetDictionaryValueType": "Value",
            "WFInput": out_attach("词典值", u_life_data),
        },
    })

    g_exist = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_exist,
            "WFControlFlowMode": 0,
            "WFCondition": 2,
            "WFNumberValue": "0",
            "WFInput": {
                "Type": "Variable",
                "Variable": {
                    "Value": {
                        "OutputName": "词典值",
                        "OutputUUID": u_life_total,
                        "Type": "ActionOutput",
                        "Aggrandizements": [{"CoercionItemClass": "WFNumberContentItem", "Type": "WFCoercionVariableAggrandizement"}],
                    },
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
    })

    u_first = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
        "WFWorkflowActionParameters": {
            "UUID": u_first,
            "WFInput": out_attach("词典值", u_life_items),
            "WFItemSpecifier": "First Item",
        },
    })
    u_rec_id = uid()
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
        "WFWorkflowActionParameters": {
            "UUID": u_rec_id,
            "WFDictionaryKey": "record_id",
            "WFGetDictionaryValueType": "Value",
            "WFInput": out_attach("来自列表的项目", u_first),
        },
    })
    actions.append(act_setvar("sync_rec_id", out_attach("词典值", u_rec_id)))

    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "ShowHeaders": True,
            "UUID": uid(),
            "WFHTTPBodyType": "File",
            "WFHTTPHeaders": {
                "Value": {
                    "WFDictionaryFieldValueItems": [
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "Authorization"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": token_str("Bearer ", var_token("feishu_token")),
                        },
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "Content-Type"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": {"Value": {"string": "application/json"}, "WFSerializationType": "WFTextTokenString"},
                        },
                    ]
                },
                "WFSerializationType": "WFDictionaryFieldValue",
            },
            "WFHTTPMethod": "PUT",
            "WFRequestVariable": var_attach("sync_body"),
            "WFURL": token_str(var_token("life_url"), "/", var_token("sync_rec_id")),
        },
    })

    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_exist,
            "WFControlFlowMode": 1,
        },
    })

    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "ShowHeaders": True,
            "UUID": uid(),
            "WFHTTPBodyType": "File",
            "WFHTTPHeaders": {
                "Value": {
                    "WFDictionaryFieldValueItems": [
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "Authorization"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": token_str("Bearer ", var_token("feishu_token")),
                        },
                        {
                            "WFItemType": 0,
                            "WFKey": {"Value": {"string": "Content-Type"}, "WFSerializationType": "WFTextTokenString"},
                            "WFValue": {"Value": {"string": "application/json"}, "WFSerializationType": "WFTextTokenString"},
                        },
                    ]
                },
                "WFSerializationType": "WFDictionaryFieldValue",
            },
            "WFHTTPMethod": "POST",
            "WFRequestVariable": var_attach("sync_body"),
            "WFURL": token_str(var_token("life_url")),
        },
    })

    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_exist,
            "WFControlFlowMode": 2,
        },
    })

    set_text_var(
        actions,
        "notify_msg",
        token_str(var_token("notify_msg"), "｜🔄 ", var_token("cur_month"), " 净结余 ¥", var_token("month_net")),
    )

    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": g_sync_biz,
            "WFControlFlowMode": 2,
        },
    })

    # 3.5 Show Completion Notification
    actions.append({
        "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
        "WFWorkflowActionParameters": {
            "WFNotificationActionTitle": "飞书记账完成",
            "WFNotificationActionBody": token_str(var_token("notify_msg")),
        },
    })

    return {
        "WFQuickActionSurfaces": [],
        "WFWorkflowActions": actions,
        "WFWorkflowClientVersion": "1505.3",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowHasShortcutInputVariables": False,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": 59719,
            "WFWorkflowIconStartColor": -12365313,
        },
        "WFWorkflowImportQuestions": [
            {
                "ActionIndex": 1,
                "Category": "Parameter",
                "DefaultValue": "YOUR_FEISHU_APP_ID",
                "ParameterKey": "WFTextActionText",
                "Text": "1/4 请输入飞书自建应用的 App ID（形如 cli_xxxxxxxxxxxxxxxx）：",
            },
            {
                "ActionIndex": 3,
                "Category": "Parameter",
                "DefaultValue": "YOUR_FEISHU_APP_SECRET",
                "ParameterKey": "WFTextActionText",
                "Text": "2/4 请输入飞书自建应用的 32 位 App Secret：",
            },
            {
                "ActionIndex": 5,
                "Category": "Parameter",
                "DefaultValue": "https://open.feishu.cn/open-apis/bitable/v1/apps/YOUR_BITABLE_APP_TOKEN_BIZ/tables/YOUR_TABLE_ID_BIZ/records",
                "ParameterKey": "WFTextActionText",
                "Text": "3/4 请输入【副业项目账本】API 地址（由 init-bitable.mjs 自动输出）：",
            },
            {
                "ActionIndex": 7,
                "Category": "Parameter",
                "DefaultValue": "https://open.feishu.cn/open-apis/bitable/v1/apps/YOUR_BITABLE_APP_TOKEN_LIFE/tables/YOUR_TABLE_ID_LIFE/records",
                "ParameterKey": "WFTextActionText",
                "Text": "4/4 请输入【日常消费账本】API 地址（若单账本可填与上面相同的地址）：",
            },
        ],
        "WFWorkflowInputContentItemClasses": [
            "WFAppContentItem", "WFAppStoreAppContentItem", "WFArticleContentItem",
            "WFContactContentItem", "WFDateContentItem", "WFEmailAddressContentItem",
            "WFFolderContentItem", "WFGenericFileContentItem", "WFImageContentItem",
            "WFiTunesProductContentItem", "WFLocationContentItem", "WFDCMapsLinkContentItem",
            "WFAVAssetContentItem", "WFPDFContentItem", "WFPhoneNumberContentItem",
            "WFRichTextContentItem", "WFSafariWebPageContentItem", "WFStringContentItem",
            "WFURLContentItem",
        ],
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowTypes": ["Watch"],
    }


def sign_shortcut(xml_plist_str: str, shortcut_name: str, unsigned_path: Path, signed_path: Path) -> None:
    # Prefer local macOS `shortcuts sign` when running on macOS
    if sys.platform == "darwin" and shutil.which("shortcuts"):
        subprocess.run(
            ["shortcuts", "sign", "--mode", "anyone", "--input", str(unsigned_path), "--output", str(signed_path)],
            check=True,
        )
        print(f"[OK] Signed via macOS `shortcuts sign`: {signed_path} ({signed_path.stat().st_size} bytes)")
        return

    # Otherwise use RoutineHub's community HubSign service
    payload = json.dumps({
        "shortcutName": shortcut_name,
        "shortcut": xml_plist_str,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://hubsign.routinehub.services/sign",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "cherri/1.0",
            "Origin": "https://routinehub.co",
            "Referer": "https://routinehub.co/",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        signed_bytes = resp.read()
    if not signed_bytes.startswith(b"AEA1"):
        raise RuntimeError(f"Unexpected signed header: {signed_bytes[:8]!r}")
    signed_path.write_bytes(signed_bytes)
    print(f"[OK] Signed via HubSign (AEA1): {signed_path} ({len(signed_bytes)} bytes)")


def main():
    parser = argparse.ArgumentParser(description="Build Feishu Bitable Auto-Bookkeeping iOS Shortcut")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to shortcut JSON config")
    parser.add_argument("--unsigned-out", type=Path, default=UNSIGNED_OUT, help="Output path for unsigned XML plist .shortcut")
    parser.add_argument("--signed-out", type=Path, default=SIGNED_OUT, help="Output path for signed AEA1 .shortcut")
    parser.add_argument("--sign", action="store_true", help="Sign the shortcut for direct iOS/macOS import")
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    shortcut_dict = build_shortcut_dict(cfg)
    xml_plist = plistlib.dumps(shortcut_dict, fmt=plistlib.FMT_XML).decode("utf-8")

    args.unsigned_out.parent.mkdir(parents=True, exist_ok=True)
    args.unsigned_out.write_text(xml_plist, encoding="utf-8")
    print(f"[OK] Generated unsigned XML plist shortcut: {args.unsigned_out} ({len(xml_plist)} bytes, {len(shortcut_dict['WFWorkflowActions'])} actions)")

    if args.sign:
        sign_shortcut(xml_plist, cfg.get("shortcut_name", "飞书双账本自动记账-通用模板"), args.unsigned_out, args.signed_out)


if __name__ == "__main__":
    main()
