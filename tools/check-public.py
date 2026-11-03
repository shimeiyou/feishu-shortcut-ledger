#!/usr/bin/env python3
"""Check public placeholders, signing provenance, local links and common secrets."""
import hashlib
import json
import plistlib
import re
from pathlib import Path
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'config/shortcut-config.example.json').read_text())
assert config['feishu']=={
    'app_id':'YOUR_FEISHU_APP_ID','app_secret':'YOUR_FEISHU_APP_SECRET',
    'record_url':'https://open.feishu.cn/open-apis/bitable/v1/apps/YOUR_BITABLE_APP_TOKEN/tables/YOUR_TABLE_ID/records'}
source=ROOT/'shortcuts/Feishu-Unified-Ledger-Unsigned.shortcut'
doc=plistlib.loads(source.read_bytes())
values=[doc['WFWorkflowActions'][q['ActionIndex']]['WFWorkflowActionParameters']['WFTextActionText'] for q in doc['WFWorkflowImportQuestions']]
assert values==list(config['feishu'].values())
receipt=json.loads((ROOT/'shortcuts/signing-receipt.json').read_text())
signed=(ROOT/'shortcuts/飞书一体账本-通用版.shortcut').read_bytes()
assert signed.startswith(b'AEA1')
assert hashlib.sha256(source.read_bytes()).hexdigest()==receipt['source_sha256']
assert hashlib.sha256(signed).hexdigest()==receipt['signed_sha256']
patterns=[r'cli_[A-Za-z0-9]{12,}',r'tbl[A-Za-z0-9]{12,}',r'gh[pousr]_[A-Za-z0-9]{20,}',r'crsr_[A-Za-z0-9]{20,}',r'-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----','/'+'home'+r'/[^\s/]+/','/'+'Users'+r'/[^\s/]+/']
files=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in p.relative_to(ROOT).parts for x in ('.git','__pycache__','private'))]
for p in files:
    if p.suffix=='.pyc' or p.name.endswith('.local.json') or p.name=='.env':continue
    try:text=p.read_text()
    except UnicodeDecodeError:continue
    for pattern in patterns:assert not re.search(pattern,text),f'Potential private identifier/secret in {p.relative_to(ROOT)}'
    if p.suffix=='.md':
        for target in re.findall(r'\]\(([^\s]+?)(?:\s+"[^"]*")?\)',text):
            if '://' in target or target.startswith('#') or target.startswith('mailto:'):continue
            target=unquote(target.split('#')[0])
            assert (p.parent/target).exists(),f'Broken relative link: {p.relative_to(ROOT)} -> {target}'
print('Public placeholders, source/signature hashes, local documentation links and common-secret scan passed.')
