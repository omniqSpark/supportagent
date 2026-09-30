"""Ephemeral fictional-case chat, isolated from ticket readers and approvals."""
import os,re,time,uuid,threading,json,base64
from urllib.parse import quote
from pathlib import Path
from domain import Ticket
from library_guidance import recommend
from chat_retrieval import retrieve, RetrievalError
from support_policy import internal_record, repeat_block, completion_labels
from chat_model import generate,status as model_status,ModelUnavailable,model_sources

ROOT=Path(__file__).parent
SESSIONS={};LOCK=threading.Lock()
PRODUCTS=('QN33','SeeControl','Controller Application','Dynamic REST Publisher')

def safe_text(value):
 if not isinstance(value,str) or len(value)>3000:raise ValueError('Use a message under 3,000 characters.')
 for key in ('OPENAI_API_KEY','FRESHDESK_API_KEY'):
  secret=os.environ.get(key,'')
  if secret and any(v in value for v in (secret,quote(secret,safe=''),base64.b64encode((secret+':X').encode()).decode())):raise ValueError('Remove credentials before continuing.')
 if re.search(r'(?i)\b(?:password|passwd|api.?key|token|secret|authorization)\s*(?:[:=]|\bis\b)\s*\S+|\b(?:sk-|sk_proj_)[A-Za-z0-9_-]{12,}|\b(?:bearer|basic)\s+[A-Za-z0-9+/=._-]{8,}',value):raise ValueError('Remove credentials before continuing.')
 if re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://|\b\d{1,3}(?:\.\d{1,3}){3}\b',value):raise ValueError('Use a fictional case without contact details, URLs or IP addresses.')
 return value.strip()

def settings():
 return {**model_status(),'products':list(PRODUCTS),'scope':'Fictional cases and product questions only. No ticket loading or sending.','knowledge':'Public code distribution: no proprietary product knowledge included. Configure an authorized local library before testing product-specific answers.','scenarios':json.loads((ROOT/'data/chat_scenarios.json').read_text(encoding='utf-8'))}


def chat(data):
 if not isinstance(data,dict) or set(data)-{'message','session_id','product','version','audience','scope'}:raise ValueError('Invalid chat request; ticket inputs are not supported.')
 if data.get('scope')!='fictional':raise ValueError('This playground accepts fictional cases and product questions only.')
 message=safe_text(data.get('message',''))
 if not message:raise ValueError('Enter a question.')
 product=data.get('product','');version=safe_text(data.get('version',''));audience=data.get('audience','customer')
 if product not in ('',)+PRODUCTS or len(version)>30 or audience not in ('customer','technician'):raise ValueError('Invalid product or audience.')
 now=time.time();sid=data.get('session_id')
 with LOCK:
  for key in list(SESSIONS):
   if now-SESSIONS[key]['time']>3600:del SESSIONS[key]
  if sid:
   if not isinstance(sid,str) or sid not in SESSIONS:raise ValueError('Chat expired. Start a new chat.')
   session=SESSIONS[sid]
   if session.get('busy'):raise ValueError('Wait for the current response.')
   if (product,version,audience)!=(session['product'],session['version'],session['audience']):raise ValueError('Start a new chat to change product, version or audience.')
  else:
   if len(SESSIONS)>=30:raise ValueError('Chat capacity reached; try again later.')
   sid=uuid.uuid4().hex;session={'messages':[],'product':product,'version':version,'audience':audience,'time':now};SESSIONS[sid]=session
  if len(session['messages'])>=24:raise ValueError('This chat reached 12 turns. Start a new chat.')
  session['busy']=True
  messages=[*session['messages'],{'role':'user','content':message}]
 try:
  users=[m['content'] for m in messages if m['role']=='user'];combined='\n'.join(users)
  # Accept explicit model/version in conversation; most recent mention supersedes prior detail.
  for text in users:
   found=[p for p in PRODUCTS if re.search(r'(?i)\b'+re.escape(p)+r'\b',text)]
   if len(found)==1:
    if product and product!=found[0]:version=''
    product=found[0]
   qn=re.search(r'(?i)\bQN\s*(\d+)\b',text)
   if qn:product='QN'+qn.group(1)
   if len(found)>1:product=''

   match=re.search(r'(?i)\b(?:version|build|v)\s*(?:is\s+)?(\d+(?:\.\d+){1,3})\b',text)
   if match:version=match.group(1)
  # Only an explicit follow-up inherits the previous technical topic.
  followup=bool(re.search(r'(?i)^(?:both|only (?:live|captured)|yes|no[,. ]|already|I (?:have |already |checked|tried)|we (?:have |already |checked|tried)|the installed version|(?:the )?version|v?\d+\.)',message.strip()))
  topic_text=combined if followup else message
  ticket=Ticket('fictional-chat','',' '.join(topic_text.split()),product_model=product,product_version=version)
  urgent=bool(re.search(r'(?i)\b(outage|breach|ransomware|hacked|security incident|public safety|emergency|(?:entire site|entire system|all lanes|all cameras|whole site|whole system) (?:are |is )?(?:down|offline)|unauthorized access)\b',combined))
  topic=topic_text
  config=model_status()
  trace={'configuration':config,'retrieval':{},'model':{'attempted':False,'passages_submitted':[]}}
  if config['mode']=='unavailable':
   error=ModelUnavailable(config['message'],'model_configuration_error');error.trace=trace;raise error
  try:retrieval=retrieve(ticket,topic,audience)
  except RetrievalError as exc:
   error=ModelUnavailable(str(exc),'retrieval_failure');trace['retrieval']={'status':'failure'};error.trace=trace;raise error
  draft,sources,needs_human=retrieval['answer'],retrieval['sources'],retrieval['needs_human']
  trace['retrieval']={k:retrieval[k] for k in ('status','candidates','missing','withheld')}
  trace['retrieval']['selected_passages']=model_sources(sources)
  completed=completion_labels(topic_text)
  repeated=repeat_block(topic_text,sources,session.get('last_source_ids',[])) or retrieval['status']=='completed_step'
  if repeated:
   draft='Thanks for checking that. A technician needs to review the result before choosing the next step; the available guidance does not establish a further procedure.'
   sources=[];needs_human=True
  mode='local';kind='simulated_response';notice='Source-only simulation — no language model was called.'
  if urgent:
   draft='This needs urgent human review. Contact your incident lead now; I cannot establish a safe technical fix from this chat.';sources=[];needs_human=True
   kind='safety_escalation';notice='Safety rule response — model bypassed for urgent human review.'
  elif repeated:
   kind='completed_step';notice='Workflow rule response — no model call; completed check needs review.'
  elif not sources:
   kind=retrieval['status'];notice='Retrieval outcome: '+kind.replace('_',' ')+'. No model call.'
  elif config['ready']:
   if any(s.get('external_model_allowed') is False for s in sources):
    error=ModelUnavailable('Selected material is not authorized for model input.','source_authorization_error');error.trace=trace;raise error
   allowed=model_sources(sources)
   try:
    for item in allowed:
     for key in ('text','passage'):
      if key in item:safe_text(item[key])
   except ValueError:
    error=ModelUnavailable('A retrieved excerpt failed the model-input safety check.','retrieval_failure');error.trace=trace;raise error from None
   try:
    result=generate(messages,allowed,product,version)
    draft=safe_text(result['answer'])
   except ModelUnavailable as exc:
    trace['model']={'attempted':exc.attempted,'passages_submitted':allowed if exc.attempted else []};exc.trace=trace;raise
   except ValueError:
    error=ModelUnavailable('The generated answer failed the content safety check.','model_validation_error',True);trace['model']={'attempted':True,'passages_submitted':allowed};error.trace=trace;raise error from None
   sources=[s for s in sources if s['id'] in result['source_ids']];needs_human=result['needs_human'];mode='openai';kind='generated_answer';notice='Generated by the configured OpenAI model. Check the cited evidence before use.'
   trace['model']={'attempted':True,'passages_submitted':allowed,'returned_source_ids':result['source_ids']}
  missing=retrieval['missing'] or ([draft] if not needs_human and '?' in draft else [])
  reason=('Urgent outage, security or public-safety indicator requires human review' if urgent else 'Previously attempted check; next documented step or outcome review is required' if repeated else 'No applicable authorized next step or verified diagnosis' if needs_human else '')
  record=internal_record(product,version,sources,'Urgent human review' if urgent else 'Technician review' if needs_human else 'Collect missing detail' if missing else 'Provide retrieved scoped guidance',missing,[reason] if reason else [],completed)
  result={'response_kind':kind,'trace':trace,'internal_record':record,'customer_reply':draft if audience=='customer' else None,'session_id':sid,'answer':draft,'sources':sources,'needs_human':needs_human,'urgent':urgent,'mode':mode,'notice':notice,'product':product,'version':version,'audience':audience,'turn':len(users)}
  with LOCK:
   session['messages']=messages+[{'role':'assistant','content':draft}];session['time']=time.time();session['last_source_ids']=[s['id'] for s in sources]
  return result
 finally:
  with LOCK:session['busy']=False
