#!/usr/bin/env python3
"""Unified v2 Shortcut: editable OCR, native JSON, explicit dates, checked writes.
Stdlib only. Deterministic UUIDs. --sign uses macOS locally, never uploads secrets.
"""
import argparse
import json
import plistlib
import re
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / 'config/shortcut-config.example.json'

def var(name): return {'Type': 'Variable', 'VariableName': name}
def attach(v): return {'Value': v, 'WFSerializationType': 'WFTextTokenAttachment'}
def tok(*parts):
    text, refs = '', {}
    for p in parts:
        if isinstance(p, str): text += p
        else:
            refs['{%d, 1}' % (len(text.encode('utf-16-le')) // 2)] = p
            text += '\ufffc'
    return {'Value': {'string': text, 'attachmentsByRange': refs}, 'WFSerializationType': 'WFTextTokenString'}

def dictionary(items):
    fields = []
    for k, kind, v in items:
        value = ({'Value': dictionary(v), 'WFSerializationType': 'WFDictionaryFieldValue'} if kind == 1
                 else v if isinstance(v, dict) and v.get('WFSerializationType') == 'WFTextTokenString' else tok(v))
        fields.append({'WFItemType': kind, 'WFKey': tok(k), 'WFValue': value})
    return {'Value': {'WFDictionaryFieldValueItems': fields}, 'WFSerializationType': 'WFDictionaryFieldValue'}

def validate_config(cfg):
    f, branches = cfg['feishu'], cfg['branches']
    for k in ('app_id', 'app_secret', 'record_url'):
        if not isinstance(f.get(k), str) or not f[k].strip(): raise ValueError('Missing feishu.' + k)
    if not re.fullmatch(r'https://open\.feishu\.cn/open-apis/bitable/v1/apps/[A-Za-z0-9_]+/tables/[A-Za-z0-9_]+/records', f['record_url']):
        raise ValueError('record_url must be an official Feishu records endpoint')
    if len(branches) != 4 or {(b['ledger'], b['sign']) for b in branches} != {('生意', 1), ('生意', -1), ('生活', 1), ('生活', -1)}:
        raise ValueError('Exactly four ledger/direction branches are required')
    if len({b['title'] for b in branches}) != 4: raise ValueError('Branch titles must be unique')
    for b in branches:
        names = [c['name'] for c in b['categories']]
        if not names or any(not n.strip() or n == '生意结余' for n in names) or len(set(names)) != len(names):
            raise ValueError('Categories must be unique, nonempty and not reserved 生意结余')

def build_shortcut_dict(cfg):
    validate_config(cfg)
    actions, questions = [], []
    def uid(): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'feishu-shortcut-ledger/v2/' + str(len(actions)))).upper()
    def act(name, **p):
        p.setdefault('UUID', uid())
        actions.append({'WFWorkflowActionIdentifier': 'is.workflow.actions.' + name, 'WFWorkflowActionParameters': p})
        return {'Type': 'ActionOutput', 'OutputUUID': p['UUID'], 'OutputName': '结果'}
    def setvar(n, v): act('setvariable', WFVariableName=n, WFInput=attach(v))
    def textvar(n, v): setvar(n, act('gettext', WFTextActionText=v))
    def cond(v, code, rhs=None):
        numeric = type(rhs) in (int, float)
        if numeric:
            v = act('math', WFInput=attach(v), WFMathOperation='×', WFMathOperand='1')
            v['OutputName'] = '计算结果'
        g = uid()
        p = dict(GroupingIdentifier=g, WFControlFlowMode=0, WFInput={'Type': 'Variable', 'Variable': attach(v)}, WFCondition=code)
        if numeric: p.update(WFNumberValue=rhs, WFConditionalLegacyComparisonBehavior=True)
        elif rhs is not None: p['WFConditionalActionString'] = rhs
        act('conditional', **p)
        return g
    def flow(g, m): act('conditional', GroupingIdentifier=g, WFControlFlowMode=m)
    def fail(msg):
        act('alert', WFAlertActionTitle='本次未确认保存', WFAlertActionMessage=msg, WFAlertActionCancelButtonShown=False)
        act('exit')
    def require(v, msg):
        g = cond(v, 101); fail(msg); flow(g, 2)
    def key(v, k): return act('getvalueforkey', WFInput=attach(v), WFDictionaryKey=k, WFGetDictionaryValueType='Value')

    act('comment', WFCommentActionText='飞书一体账本通用版 v2。只连接自己的飞书应用和一张表。'
        '\n导入时填写 App ID、App Secret、记录 API 地址。分享前移除自己的配置。'
        '\n截图→OCR→选择候选→修改金额→选择收支及分类→保存。月结余刷新另行配置。')
    for n, label in [('app_id', '飞书应用 App ID'), ('app_secret', '飞书应用 App Secret'), ('record_url', '一体账本记录 API 地址')]:
        i = len(actions); textvar(n, cfg['feishu'][n])
        questions.append({'ActionIndex': i, 'Category': 'Parameter', 'DefaultValue': '', 'ParameterKey': 'WFTextActionText', 'Text': '请输入自己的' + label + '：'})
        require(var(n), '请先填写' + label)
        g = cond(var(n), 99, 'YOUR_')
        fail('请先替换导入配置中的占位符：' + label); flow(g, 2)

    shot = act('takescreenshot')
    ocr = act('extracttextfromimage', WFImage=attach(shot))
    match = act('text.match', WFMatchTextPattern=r'(?<![\d.])\d+(?:\.\d{1,2})?(?![\d.])', text=tok(ocr))
    count = act('count', Input=attach(match))
    g = cond(count, 2, 0)
    setvar('money', act('choosefromlist', WFChooseFromListActionPrompt='选择本次金额（下一步可修改）', WFInput=attach(match)))
    setvar('money', act('ask', WFAskActionPrompt='确认金额（可修改；输入正数，收入/支出下一步选择）', WFInputType='Number',
        WFAskActionDefaultAnswer=tok(var('money')), WFAskActionDefaultAnswerNumber=attach(var('money')),
        WFAskActionAllowsDecimalNumbers=True, WFAskActionAllowsNegativeNumbers=False))
    flow(g, 1)
    setvar('money', act('ask', WFAskActionPrompt='没有检测到金额，请手动输入正数：', WFInputType='Number',
        WFAskActionAllowsDecimalNumbers=True, WFAskActionAllowsNegativeNumbers=False))
    flow(g, 2)
    g = cond(var('money'), 2, 0); flow(g, 1); fail('金额必须大于零，请重新运行并检查金额。'); flow(g, 2)
    value_text = act('gettext', WFTextActionText=tok(var('money')))
    valid = act('text.match', WFMatchTextPattern=r'^\d+(?:\.\d{1,2})?$', text=tok(value_text))
    require(valid, '金额只能有最多两位小数，请重新输入。')

    g = uid()
    act('choosefrommenu', GroupingIdentifier=g, WFControlFlowMode=0,
        WFMenuItems=[b['title'] for b in cfg['branches']], WFMenuPrompt=tok('记账 ¥', var('money')))
    for b in cfg['branches']:
        act('choosefrommenu', GroupingIdentifier=g, WFControlFlowMode=1, WFMenuItemTitle=b['title'])
        textvar('账本', b['ledger']); textvar('收支类型', '收入' if b['sign'] > 0 else '支出')
        setvar('金额', act('math', WFInput=attach(var('money')), WFMathOperation='×', WFMathOperand=str(b['sign'])))
        sub = uid()
        act('choosefrommenu', GroupingIdentifier=sub, WFControlFlowMode=0, WFMenuItems=[c['name'] for c in b['categories']], WFMenuPrompt='选择分类')
        for c in b['categories']:
            act('choosefrommenu', GroupingIdentifier=sub, WFControlFlowMode=1, WFMenuItemTitle=c['name'])
            textvar('分类', c['name'])
            if c.get('ask_note', False) or c['name'] == '其他':
                setvar('event', act('ask', WFAskActionPrompt='请输入具体事件或收入来源：', WFInputType='Text'))
            else: textvar('event', c['name'])
        act('choosefrommenu', GroupingIdentifier=sub, WFControlFlowMode=2)
    act('choosefrommenu', GroupingIdentifier=g, WFControlFlowMode=2)
    require(var('event'), '请填写具体事件或收入来源。')

    epoch = act('date', WFDateActionMode='Specified Date', WFDateActionDate='1970-01-01T00:00:00Z')
    now = act('date', WFDateActionMode='Current Date')
    seconds = act('gettimebetweendates', WFTimeUntilFromDate=tok(epoch), WFInput=tok(now), WFTimeUntilUnit='Seconds')
    setvar('记账时间', act('math', WFInput=attach(seconds), WFMathOperation='×', WFMathOperand='1000'))
    token = act('downloadurl', WFHTTPMethod='POST', WFHTTPBodyType='JSON', ShowHeaders=False,
        WFURL='https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        WFJSONValues=dictionary([('app_id', 0, var('app_id')), ('app_secret', 0, var('app_secret'))]))
    code = key(token, 'code'); require(code, '授权响应异常，未提交账目。')
    g = cond(code, 4, 0)
    setvar('feishu_token', key(token, 'tenant_access_token'))
    flow(g, 1); fail('飞书授权失败，未提交账目。请检查应用凭证和权限。'); flow(g, 2)
    require(var('feishu_token'), '没有获得飞书授权，未提交账目。')
    record = act('downloadurl', WFHTTPMethod='POST', WFHTTPBodyType='JSON', ShowHeaders=False, WFURL=tok(var('record_url')),
        WFHTTPHeaders=dictionary([('Authorization', 0, tok('Bearer ', var('feishu_token'))), ('Content-Type', 0, 'application/json')]),
        WFJSONValues=dictionary([('fields', 1, [('事件', 0, var('event')), ('时间', 3, var('记账时间')), ('收支', 3, var('金额')),
            ('账本', 0, var('账本')), ('分类', 0, var('分类')), ('来源', 0, '快捷指令')])]))
    uncertain = '未确认保存结果，请先查看飞书账目，勿直接重复提交。'
    code = key(record, 'code'); require(code, uncertain)
    g = cond(code, 4, 0)
    data = key(record, 'data'); require(data, uncertain)
    rec = key(data, 'record'); require(rec, uncertain)
    rid = key(rec, 'record_id'); require(rid, uncertain)
    act('notification', WFNotificationActionTitle='飞书记账完成',
        WFNotificationActionBody=tok(var('账本'), ' · ', var('分类'), ' ', var('收支类型'), ' ¥', var('money'), '（', var('event'), '）'))
    flow(g, 1); fail('飞书未确认保存成功，请先核对账目和权限，勿直接重复提交。'); flow(g, 2)
    return {'WFWorkflowActions': actions, 'WFWorkflowName': cfg['shortcut_name'], 'WFWorkflowClientVersion': '5037.111',
        'WFWorkflowMinimumClientVersion': 900, 'WFWorkflowMinimumClientVersionString': '900',
        'WFWorkflowHasOutputFallback': False, 'WFWorkflowHasShortcutInputVariables': False,
        'WFWorkflowInputContentItemClasses': [], 'WFWorkflowOutputContentItemClasses': [], 'WFQuickActionSurfaces': [],
        'WFWorkflowTypes': ['WFWorkflowTypeShowInSearch'],
        'WFWorkflowIcon': {'WFWorkflowIconGlyphNumber': 59719, 'WFWorkflowIconStartColor': -12365313}, 'WFWorkflowImportQuestions': questions}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    p.add_argument('--output', type=Path, default=ROOT / 'shortcuts/Feishu-Unified-Ledger-Unsigned.shortcut')
    p.add_argument('--sign', action='store_true', help='Sign locally with macOS shortcuts sign; no remote upload')
    args = p.parse_args()
    cfg = json.loads(args.config.read_text())
    if args.config.resolve() != DEFAULT_CONFIG.resolve() and args.output.parent.resolve() == (ROOT / 'shortcuts').resolve():
        p.error('Custom config: use --output shortcuts/private/MyLedger.shortcut to keep credentials out of Git')
    result = build_shortcut_dict(cfg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(plistlib.dumps(result, fmt=plistlib.FMT_XML))
    if args.sign:
        if not shutil.which('shortcuts'): p.error('Signing needs macOS Shortcuts. Unsigned source generated; see docs/03-iphone-shortcut-guide.md')
        signed = args.output.with_name(args.output.stem.replace('-Unsigned', '') + '.signed.shortcut')
        subprocess.run(['shortcuts', 'sign', '--mode', 'anyone', '--input', str(args.output), '--output', str(signed)], check=True)
    print(f'Built {len(result["WFWorkflowActions"])} actions: {args.output.name}')

if __name__ == '__main__': main()
