"""Local review decisions only. No connector dependency or production mutations."""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).parent/'local_reviews'
LOCK=threading.Lock()


def read(name, default):
    path=ROOT/name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def listing():
    with LOCK:
        rows=read('history.json',[]);decisions=read('decisions.json',{})
        return {'items':[{**r,**decisions.get(r['id'],{})} for r in rows], 'summary':read('import_summary.json',{})}


def save(data):
    if not isinstance(data,dict):raise ValueError('Invalid review')
    tid=data.get('id');decision=data.get('decision');reply=data.get('proposed_reply');note=data.get('note','')
    if not isinstance(tid,str) or decision not in ('approved','edited','rejected','hold'):raise ValueError('Choose a review decision')
    if not isinstance(reply,str) or not isinstance(note,str) or len(reply)>12000 or len(note)>3000:raise ValueError('Review text is too long or invalid')
    if decision in ('approved','edited') and not reply.strip():raise ValueError('Reply text is required for approval')
    if re.search(r'(?i)(?:password|api.?key|token|secret)\s*[:=]',reply+' '+note):raise ValueError('Remove credential content before saving')
    with LOCK:
        rows=read('history.json',[]);record=next((r for r in rows if r['id']==tid),None)
        if not record:raise ValueError('Historical example not found')
        if decision in ('approved','edited') and (not record['historical_reply'] or 'Incomplete history' in record['flags']):raise ValueError('This record needs more evidence before approval')
        if decision in ('approved','edited') and any('Out-of-office' in f for f in record['flags']):raise ValueError('Automatic replies cannot be approved as support examples')
        decisions=read('decisions.json',{})
        previous=decisions.get(tid,{})
        if data.get('revision',0)!=previous.get('revision',0):raise ValueError('Review changed in another tab; reload before saving')
        decisions[tid]={'decision':decision,'proposed_reply':reply,'note':note,'reviewed_at':datetime.now(timezone.utc).isoformat(),'revision':previous.get('revision',0)+1,'approval_scope':'Local style example only; no technical-source approval or sending permission'}
        ROOT.mkdir(exist_ok=True);tmp=ROOT/'decisions.tmp';tmp.write_text(json.dumps(decisions,indent=2),encoding='utf-8');tmp.replace(ROOT/'decisions.json')
        return decisions[tid]
