"""Retrieve only reviewed excerpts. The full extracted corpus is discovery-only."""
import hashlib,json,re
from pathlib import Path
from library_guidance import recommend
ROOT=Path(__file__).parent/'library-review'

class RetrievalError(Exception):pass

def read(name):
 try:return json.loads((ROOT/name).read_text(encoding='utf-8'))
 except (OSError,ValueError):raise RetrievalError('Reviewed knowledge index is missing or unreadable.') from None

def verify(c):
 inv={s['source_id']:s for s in read('source_inventory.json')}
 try:
  if hashlib.sha256(Path(inv[c['source_id']]['path']).read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError()
  if c.get('passage') and hashlib.sha256(c['passage'].encode()).hexdigest()!=c['passage_sha256']:raise ValueError()
 except (OSError,KeyError,ValueError):raise RetrievalError('A matched source or reviewed excerpt changed or cannot be verified.') from None

def retrieve(ticket,topic,audience):
 result=dict(status='no_relevant_source',sources=[],missing=[],candidates=[],withheld=[],answer='',needs_human=True)
 def done(answer,sources=(),missing=(),status='matched',human=False):
  result.update(answer=answer,sources=list(sources),missing=list(missing),status=status,needs_human=human);return result
 # Replay is a descriptive question, not authorization to execute a procedure.
 if re.search(r'(?i)\b(?:replay\w*|resen[dt]\w*|recover\w*)\b',topic) and re.search(r'(?i)events?|archive',topic):
  c=read('replay_guidance.json');verify(c);c['citation']='S03, PDF p. 2, '+c['section'];result['candidates']=['R01']
  question='Which event-delivery component is involved?' if ticket.product_model!='Dynamic REST Publisher' else 'What time range is missing?'
  return done(c['text']+' '+question,[c],[question],status='partial_answer')
 guidance=recommend(ticket)
 result['withheld']=guidance['withheld']
 eligible=guidance['customer']+(guidance['technician'] if audience=='technician' else [])
 if any('cannot be verified' in w['reason'] or 'Source changed' in w['reason'] or 'unavailable' in w['reason'] for w in guidance['withheld']):raise RetrievalError('Matched library source is unavailable or changed.')
 if eligible:
  item=dict(eligible[0]);item['external_model_allowed']=True
  original=next(c for c in read('proposed_guidance.json') if c['id']==item['id'])
  item['passage']=original['source_fact'];item['passage_kind']='Reviewed summary of cited passage; not a verbatim excerpt'
  result['candidates']=[item['id']]
  return done(item['text'],[item])
 if any('already reported attempted' in w['reason'] for w in guidance['withheld']) or (any('already supplied' in w['reason'] for w in guidance['withheld']) and not any('version' in w['reason'].lower() for w in guidance['withheld'])):
  return done('Thanks, that detail is already noted. A technician needs to review the result before selecting the next documented step.',status='completed_step',human=True)
 cards=read('dialogflow_verified.json');matches=[c for c in cards if re.search(c['pattern'],topic,re.I)]
 result['candidates']=[c['id'] for c in matches]
 if matches:
  if len(matches)>1:return done('Please ask about one technical topic at a time.',missing=['Which technical topic should we address first?'],status='clarification')
  c=matches[0]
  if c['status']!='sandbox_enabled':return done('This topic has no approved answer yet. A technician needs to review the applicable guidance.',status='approval_required',human=True)
  verify(c)
  if not ticket.product_model:return done('Which product model are you working with?',missing=['Product model'],status='clarification')
  if ticket.product_model!=c['product']:return done('The retrieved document covers '+c['product']+'. I need guidance for your identified product before recommending a step.',status='scope_mismatch',human=True)
  if c['version'] and ticket.product_version and ticket.product_version!=c['version']:
   return done('The retrieved manual covers '+c['version']+'. It does not establish applicability to your installed version; this is not evidence of incompatibility.',status='scope_mismatch',human=True)
  item=dict(id=c['id'],title=c['name'],text=c['text'],passage=c['passage'],passage_kind='Verified document excerpt',citation=f"{c['source_id']}, PDF p. {c['page']}",filename=c['source_filename'],applicability=c['product']+' '+c['version']+'; descriptive answer only, not a procedure',limitations=c['finding'],approval=c['authorization'],external_model_allowed=c['external_model_allowed'])
  return done(item['text'],[item])
 if not ticket.product_model:return done('Which product model are you working with?',missing=['Product model'],status='clarification')
 version_reasons=[w for w in guidance['withheld'] if 'version' in w['reason'].lower() or 'build' in w['reason'].lower()]
 if version_reasons:
  if not ticket.product_version:return done('Which software version is installed? I need it to check the applicable procedure.',missing=['Installed software version for the requested procedure'],status='clarification')
  return done('The retrieved procedure has not been verified for this product build. That does not establish incompatibility; a technician needs to confirm applicability.',status='scope_mismatch',human=True)
 return done('No approved passage was retrieved for this question. A technician needs to review it before I suggest a technical change.',status='no_relevant_source',human=True)
