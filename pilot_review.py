"""Local human scoring, separate from style approvals and production actions."""
import json
from datetime import datetime,timezone
import local_review
FIELDS=('reply_usefulness','classification','routing','escalation')

def listing():
 with local_review.LOCK:
  rows=local_review.read('pilot_trial.json',[]);scores=local_review.read('pilot_scores.json',{})
  retests=local_review.read('feedback_retests.json',{})
  metrics={}
  for field in FIELDS:
   values=[s[field] for s in scores.values() if s.get(field) in ('pass','fail') and any(r['id']==s['id'] for r in rows)]
   metrics[field]={'passed':values.count('pass'),'scored':len(values),'percent':round(100*values.count('pass')/len(values),1) if values else None}
  return {'items':[{**r,'score':scores.get(r['id'],{}),'retest':retests.get(r['id'])} for r in rows],'metrics':metrics}

def save(data):
 if not isinstance(data,dict) or any(data.get(f) not in ('pass','fail','unsure') for f in FIELDS):raise ValueError('Invalid scores')
 if not isinstance(data.get('note',''),str) or len(data.get('note',''))>3000:raise ValueError('Invalid note')
 with local_review.LOCK:
  rows=local_review.read('pilot_trial.json',[])
  if data.get('id') not in [r['id'] for r in rows]:raise ValueError('Unknown trial ticket')
  scores=local_review.read('pilot_scores.json',{});old=scores.get(data['id'],{})
  if data.get('revision',0)!=old.get('revision',0):raise ValueError('Stale review')
  score={f:data[f] for f in FIELDS};score.update(id=data['id'],note=data.get('note',''),revision=old.get('revision',0)+1,reviewed_at=datetime.now(timezone.utc).isoformat())
  scores[data['id']]=score
  path=local_review.ROOT/'pilot_scores.tmp';path.write_text(json.dumps(scores,indent=2),encoding='utf-8');path.replace(local_review.ROOT/'pilot_scores.json')
  return score
