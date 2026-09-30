"""Read an ES export without extracting files or executing bot fulfillment."""
import json,re,zipfile,hashlib,argparse
from pathlib import Path,PurePosixPath
from collections import Counter
ROOT=Path(__file__).parent

def clean(value):
 if not isinstance(value,str):return ''
 value=re.sub(r'https?://\S+','[link omitted]',value)
 value=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[email omitted]',value)
 value=re.sub(r'(?i)\b(password|passwd|api.?key|secret|token|authorization)\s*[:=]\s*[^\s,;]+',r'\1=[withheld]',value)
 value=re.sub(r'\b\d{1,3}(?:\.\d{1,3}){3}\b','[IP omitted]',value)
 return value

def inspect(path):
 with zipfile.ZipFile(path) as z:
  entries=z.infolist()
  if len(entries)>5000 or sum(e.file_size for e in entries)>20_000_000:raise ValueError('Export exceeds import limits')
  names=set()
  for e in entries:
   p=PurePosixPath(e.filename.replace('\\','/'))
   if p.is_absolute() or '..' in p.parts or ':' in e.filename or e.filename in names or e.file_size>2_000_000 or (e.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe archive entry')
   names.add(e.filename)
  if 'agent.json' not in names or 'package.json' not in names:raise ValueError('Expected a Dialogflow ES agent export')
  agent=json.loads(z.read('agent.json'));records=[]
  for filename in sorted(names):
   if not filename.startswith('intents/') or not filename.endswith('.json') or '_usersays_' in filename:continue
   d=json.loads(z.read(filename));name=clean(d.get('name',''))
   phrase_files=[n for n in sorted(names) if n.startswith(filename[:-5]+'_usersays_') and n.endswith('.json')]
   phrases=[]
   for pf in phrase_files:
    for phrase in json.loads(z.read(pf)):
     text=''.join(part.get('text','') for part in phrase.get('data',[]))
     phrases.append({'text':'[Credential-related training phrase withheld]' if re.search(r'(?i)password|passwd|credentials?|api.?key|token|secret',text) else clean(text),'language':pf.rsplit('_usersays_',1)[-1][:-5]})
   answer_groups=[];rich=0;flags=[];parameters=[];contexts=[]
   credential_name=bool(re.search(r'(?i)password|passwd|credentials|user and password',name))
   if credential_name:flags.append('Credential-related intent: answer withheld')
   for response in d.get('responses',[]):
    texts=[]
    for msg in response.get('messages',[]):
     if str(msg.get('type'))=='0':
      speech=msg.get('speech',[]);speech=[speech] if isinstance(speech,str) else speech
      for text in speech:
       if credential_name or re.search(r'(?i)\bpassword|passwd|credentials?|api.?key|token|secret\b',text):
        texts.append('[Credential-related answer withheld for separate review]')
        if 'Credential-related answer withheld' not in flags:flags.append('Credential-related answer withheld')
       else:texts.append(clean(text))
     else:rich+=1
    answer_groups.append({'texts':texts,'action':clean(response.get('action','')),'reset_contexts':bool(response.get('resetContexts'))})
    parameters.extend({'name':clean(p.get('name','')),'entity':clean(p.get('dataType','')),'required':bool(p.get('required')),'prompts':['[Credential-related prompt withheld]' if re.search(r'(?i)password|passwd|credentials?|api.?key|token|secret',t) else clean(t) for t in p.get('prompts',[]) if isinstance(t,str)]} for p in response.get('parameters',[]))
    contexts.extend({'name':clean(c.get('name','')),'lifespan':c.get('lifespan')} for c in response.get('affectedContexts',[]))
   plain=' '.join(t for g in answer_groups for t in g['texts'])
   if d.get('webhookUsed') or d.get('webhookForSlotFilling'):flags.append('Webhook enabled: exported replies may differ from live fulfillment')
   if d.get('contexts') or contexts or d.get('parentId') or parameters:flags.append('Context or parameter behavior must be preserved')
   if re.search(r'(?i)restart|reboot|enable|disable|change|adjust|install|configure|click|go to|settings',plain):flags.append('Technical procedure: verify product/version and source approval')
   if re.search(r'\$[A-Za-z_]|#[A-Za-z_]',plain):flags.append('Response contains variable placeholders')
   if rich:flags.append('Rich content present; links/payloads not executed or imported')
   records.append({'id':clean(d.get('id','')),'name':name,'training_phrases':phrases,'response_groups':answer_groups,'input_contexts':[clean(c) for c in d.get('contexts',[])],'output_contexts':contexts,'parameters':parameters,'parent_id':clean(d.get('parentId','')),'root_parent_id':clean(d.get('rootParentId','')),'webhook':bool(d.get('webhookUsed')),'fallback':bool(d.get('fallbackIntent')),'rich_messages':rich,'flags':flags,'approval':'pending','enabled_for_chat':False})
  summary={'format':'Dialogflow ES','language':clean(agent.get('language','')),'export_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'intents':len(records),'training_phrases':sum(len(r['training_phrases']) for r in records),'text_answer_variants':sum(len(g['texts']) for r in records for g in r['response_groups']),'webhook_enabled':sum(r['webhook'] for r in records),'context_or_parameter_intents':sum(bool(r['input_contexts'] or r['output_contexts'] or r['parameters'] or r['parent_id']) for r in records),'credential_flagged_intents':sum(any('Credential' in f for f in r['flags']) for r in records),'rich_messages':sum(r['rich_messages'] for r in records),'fallback_intents':sum(r['fallback'] for r in records),'enabled_for_chat':0,'custom_smalltalk_present':any('Smalltalk' in n for n in names),'entity_definition_files':sum(n.startswith('entities/') and '_entries_' not in n for n in names),'knowledge_base_references':len(agent.get('enabledKnowledgeBaseNames') or [])}
  return {'summary':summary,'items':records}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('archive');args=parser.parse_args();result=inspect(args.archive)
 (ROOT/'local_reviews').mkdir(exist_ok=True)
 (ROOT/'local_reviews/dialogflow_import.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result['summary'],indent=2))
if __name__=='__main__':main()
