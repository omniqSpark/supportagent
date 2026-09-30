"""Locally verified replacements; original export answers are never executable guidance."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).parent/'library-review'
def cards():
 try:return json.loads((ROOT/'dialogflow_verified.json').read_text(encoding='utf-8'))
 except (OSError,ValueError):return []
def lookup(message,product,version):
 matches=[c for c in cards() if re.search(c['pattern'],message,re.I)]
 if not matches:return None
 if len(matches)>1:return ('Please ask about one technical topic at a time.',[],False)
 c=matches[0]
 if c['status']!='sandbox_enabled':return ('This topic needs a support specialist to verify the applicable guidance before I recommend a change.',[],True)
 if not product:return ('Which product model are you working with?',[],False)
 if product!=c['product']:return ('This source covers a different product. A support specialist needs to confirm applicable guidance.',[],True)
 if c['version'] and not version:return ('Which software version is installed?',[],False)
 if c['version'] and version!=c['version']:return ('This source covers version '+c['version']+'. A support specialist needs to confirm guidance for your version.',[],True)
 try:
  inventory={s['source_id']:s for s in json.loads((ROOT/'source_inventory.json').read_text(encoding='utf-8'))}
  if hashlib.sha256(Path(inventory[c['source_id']]['path']).read_bytes()).hexdigest()!=c['source_sha256']:raise ValueError()
 except (OSError,ValueError,KeyError):return ('The reviewed source cannot be verified. A support specialist needs to check it.',[],True)
 source=dict(id=c['id'],title=c['name'],text=c['text'],citation=f"{c['source_id']}, PDF p. {c['page']}",filename=c['source_filename'],applicability=c['product']+' '+c['version'],limitations=c['finding'],approval=c['authorization'],external_model_allowed=False)
 return (c['text'],[source],False)
def listing(data):
 reviewed={c['intent_id']:c for c in cards()}
 for item in data.get('items',[]):
  c=reviewed.get(item.get('id'))
  if c:item['review']={k:c.get(k,'') for k in ('status','text','finding','source_id','page')}
 data.setdefault('summary',{})['verified_enabled']=sum(c['status']=='sandbox_enabled' for c in reviewed.values())
 data['summary']['reviewed']=len(reviewed)
 return data
