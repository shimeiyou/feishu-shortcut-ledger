import copy
import importlib.util
import json
import plistlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder', ROOT / 'tools/build-shortcut.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
CFG = json.loads((ROOT / 'config/shortcut-config.example.json').read_text())


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.doc = plistlib.loads((ROOT / 'shortcuts/Feishu-Unified-Ledger-Unsigned.shortcut').read_bytes())
        self.actions = self.doc['WFWorkflowActions']

    def test_reproducible_and_all_references_resolve(self):
        self.assertEqual(self.doc, b.build_shortcut_dict(CFG))
        ids = [a['WFWorkflowActionParameters']['UUID'] for a in self.actions]
        self.assertEqual(len(ids), len(set(ids)))
        def refs(x):
            if isinstance(x, dict):
                if 'OutputUUID' in x: yield x['OutputUUID']
                for v in x.values(): yield from refs(v)
            elif isinstance(x, list):
                for v in x: yield from refs(v)
        self.assertTrue(set(refs(self.actions)) <= set(ids))

    def test_groups_and_import_questions(self):
        stack = []
        for a in self.actions:
            p = a['WFWorkflowActionParameters']; mode = p.get('WFControlFlowMode')
            if mode == 0: stack.append(p['GroupingIdentifier'])
            elif mode in (1, 2):
                self.assertEqual(stack[-1], p['GroupingIdentifier'])
                if mode == 2: stack.pop()
        self.assertFalse(stack)
        self.assertEqual(len(self.doc['WFWorkflowImportQuestions']), 3)
        for q in self.doc['WFWorkflowImportQuestions']:
            self.assertTrue(self.actions[q['ActionIndex']]['WFWorkflowActionIdentifier'].endswith('.gettext'))

    def test_numeric_zero_and_native_json(self):
        numbers = [a['WFWorkflowActionParameters'] for a in self.actions if 'WFNumberValue' in a['WFWorkflowActionParameters']]
        self.assertTrue(numbers)
        for p in numbers:
            self.assertIs(type(p['WFNumberValue']), int)
            self.assertEqual(p['WFInput']['Variable']['Value']['Type'], 'ActionOutput')
        http = [a['WFWorkflowActionParameters'] for a in self.actions if a['WFWorkflowActionIdentifier'].endswith('.downloadurl')]
        self.assertEqual(len(http), 2)  # no per-phone monthly synchronization
        self.assertTrue(all(p['WFHTTPBodyType'] == 'JSON' and 'WFRequestVariable' not in p for p in http))
        self.assertEqual(http[1]['WFJSONValues']['Value']['WFDictionaryFieldValueItems'][0]['WFItemType'], 1)
        self.assertEqual(next(a['WFWorkflowActionParameters']['WFDateActionDate'] for a in self.actions if 'WFDateActionDate' in a['WFWorkflowActionParameters']), '1970-01-01T00:00:00Z')

    def run_flow(self, branch=0, category=0, ocr='实付 ¥25.50', amount=25.50, note='服务 "A"\n第二行', token=None, record=None):
        """Execute the generated plist graph with external actions mocked (not iOS)."""
        cfg = copy.deepcopy(CFG)
        cfg['feishu'] = {'app_id': 'cli_example', 'app_secret': 'synthetic-test-only',
            'record_url': 'https://open.feishu.cn/open-apis/bitable/v1/apps/ExampleBase/tables/tblExample/records'}
        actions = b.build_shortcut_dict(cfg)['WFWorkflowActions']
        variables, outputs, http, notifications = {}, {}, [], []
        endpoints = token if token is not None else {'code': 0, 'tenant_access_token': 'fixture-token'}
        response = record if record is not None else {'code': 0, 'data': {'record': {'record_id': 'fixture-record'}}}
        stack, groups = [], {}
        for i, a in enumerate(actions):
            p = a['WFWorkflowActionParameters']; m = p.get('WFControlFlowMode')
            if m == 0: stack.append((p['GroupingIdentifier'], i, []))
            elif m == 1: stack[-1][2].append(i)
            elif m == 2:
                gid, start, branches = stack.pop(); groups[gid] = (start, branches, i)
        def value(x):
            if not isinstance(x, dict): return x
            if x.get('Type') == 'Variable' and 'VariableName' in x: return variables.get(x['VariableName'])
            if x.get('Type') == 'ActionOutput': return outputs.get(x['OutputUUID'])
            if 'Variable' in x: return value(x['Variable'])
            if 'Value' in x:
                if x.get('WFSerializationType') == 'WFTextTokenString':
                    v=x['Value']; text=v['string']
                    for _, ref in sorted(v.get('attachmentsByRange', {}).items(), key=lambda k:int(k[0][1:].split(',')[0]), reverse=True):
                        pos=int(_[1:].split(',')[0]); result=value(ref)
                        text=text[:pos]+str(result if result is not None else '')+text[pos+1:]
                    return text
                return value(x['Value'])
            if 'WFDictionaryFieldValueItems' in x:
                result={}
                for f in x['WFDictionaryFieldValueItems']:
                    v=value(f['WFValue']); result[value(f['WFKey'])]=float(v) if f['WFItemType']==3 else v
                return result
            return x
        i=0
        while i<len(actions):
            a=actions[i]; p=a['WFWorkflowActionParameters']; name=a['WFWorkflowActionIdentifier'].split('actions.')[1]; out=None
            mode=p.get('WFControlFlowMode')
            if name in ('conditional','choosefrommenu'):
                start, branches, end = groups[p['GroupingIdentifier']]
                if mode==0:
                    if name=='conditional':
                        v=value(p['WFInput']); code=p['WFCondition']; rhs=p.get('WFNumberValue',p.get('WFConditionalActionString'))
                        truth={101: v is None or v=='' or v==[], 99: str(rhs) in str(v), 4:v==rhs, 2:False}
                        ok=(float(v)>float(rhs)) if code==2 else truth[code]
                        if not ok: i=(branches[0]+1 if branches else end+1); continue
                    else:
                        selected=branch if len(p['WFMenuItems'])==4 and p.get('WFMenuPrompt')!='选择分类' else category
                        i=branches[selected]+1;continue
                elif mode==1: i=end+1;continue
            elif name=='gettext': out=value(p['WFTextActionText'])
            elif name=='setvariable': variables[p['WFVariableName']]=value(p['WFInput'])
            elif name=='takescreenshot': out='mock screenshot'
            elif name=='extracttextfromimage': out=ocr
            elif name=='text.match': out=re.findall(p['WFMatchTextPattern'],str(value(p['text'])))
            elif name=='count': out=len(value(p['Input']))
            elif name=='choosefromlist': out=value(p['WFInput'])[0]
            elif name=='ask': out=amount if p.get('WFInputType')=='Number' else note
            elif name=='math': out=float(value(p['WFInput']))*float(p['WFMathOperand'])
            elif name=='date': out=0 if p['WFDateActionMode']=='Specified Date' else 1793505600
            elif name=='gettimebetweendates': out=float(value(p['WFInput']))-float(value(p['WFTimeUntilFromDate']))
            elif name=='getvalueforkey': out=(value(p['WFInput']) or {}).get(p['WFDictionaryKey'])
            elif name=='downloadurl':
                http.append(value(p['WFJSONValues']));out=endpoints if len(http)==1 else response
            elif name=='notification': notifications.append(value(p['WFNotificationActionBody']))
            elif name=='exit': break
            outputs[p['UUID']]=out;i+=1
        return http,notifications

    def test_all_four_directions_and_editable_ocr(self):
        for i, branch in enumerate(CFG['branches']):
            with self.subTest(branch=branch['title']):
                http, notice=self.run_flow(branch=i,amount=12.34)
                self.assertEqual(len(notice),1);self.assertEqual(len(http),2)
                f=http[1]['fields'];self.assertEqual(f['收支'],branch['sign']*12.34)
                self.assertEqual(f['账本'],branch['ledger']);self.assertEqual(f['时间'],1793505600000)

    def test_no_ocr_manual_and_escaped_note(self):
        http,notice=self.run_flow(ocr='无金额',amount=7.25)
        self.assertEqual(http[1]['fields']['收支'],7.25);self.assertTrue(notice)
        self.assertEqual(http[1]['fields']['事件'],'服务 "A"\n第二行')

    def test_invalid_amount_or_blank_note_no_http(self):
        for amount in [0,-1,1.234]: self.assertFalse(self.run_flow(amount=amount)[0])
        self.assertFalse(self.run_flow(note='')[0])

    def test_failed_or_uncertain_response_never_notifies(self):
        self.assertEqual(len(self.run_flow(token={'code':999})[0]),1)
        for record in [{'code':1254045},{},{'code':0},{'code':0,'data':{}},{'code':0,'data':{'record':{}}}]:
            http,notice=self.run_flow(record=record);self.assertEqual(len(http),2);self.assertFalse(notice)

    def test_official_endpoint_only(self):
        cfg=copy.deepcopy(CFG);cfg['feishu']['record_url']='https://example.com/collect'
        self.assertRaises(ValueError,b.build_shortcut_dict,cfg)

if __name__=='__main__': unittest.main()
