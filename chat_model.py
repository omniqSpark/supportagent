"""OpenAI Responses transport. Sanitized errors; no ticket access, writes, or logs."""
import json,os,re
from support_policy import POLICY
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError,URLError

class ModelUnavailable(Exception):
 def __init__(self,message,code='model_api_error',attempted=False):
  super().__init__(message);self.code=code;self.attempted=attempted;self.trace={}
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def status():
 provider=os.environ.get('CHAT_PROVIDER','local').strip().lower()
 key=os.environ.get('OPENAI_API_KEY','').strip();model=os.environ.get('OPENAI_MODEL','').strip()
 key_present=bool(key) and key!='replace-locally'
 model_valid=bool(re.fullmatch(r'[A-Za-z0-9._:-]{1,100}',model))
 consent=os.environ.get('CHAT_ALLOW_PRODUCT_EXCERPTS','').lower()=='true'
 issues=[]
 if provider not in ('local','openai'):issues.append('CHAT_PROVIDER must be local or openai')
 if not key_present:issues.append('OPENAI_API_KEY is missing or a placeholder')
 if not model_valid:issues.append('OPENAI_MODEL is missing or invalid')
 if not consent:issues.append('CHAT_ALLOW_PRODUCT_EXCERPTS must be true for model calls')
 ready=provider=='openai' and not issues
 return dict(mode='openai' if ready else 'local' if provider=='local' else 'unavailable',ready=ready,
  provider=provider,key_present=key_present,model_configured=model_valid,excerpt_consent=consent,configuration_issues=issues,
  message='Real model mode configured; API access is verified on the first successful request.' if ready else 'Source-only simulation selected (CHAT_PROVIDER=local). No model calls.' if provider=='local' else 'Model configuration error: '+'; '.join(issues),
  precedence='Process environment overrides .env; restart after changes.')

def model_sources(sources):
 return [{k:s[k] for k in ('id','title','text','passage','passage_kind','citation','applicability','limitations') if k in s} for s in sources]

def generate(messages,sources,product,version):
 if not status()['ready']:raise ModelUnavailable('Model configuration error: '+'; '.join(status()['configuration_issues']),'model_configuration_error')
 key=os.environ['OPENAI_API_KEY'];model=os.environ['OPENAI_MODEL'].strip()
 schema={'type':'object','properties':{'answer':{'type':'string'},'source_ids':{'type':'array','items':{'type':'string'}},'needs_human':{'type':'boolean'}},'required':['answer','source_ids','needs_human'],'additionalProperties':False}
 instructions=POLICY+' Answer supported parts even if some context is missing. Missing version is not incompatibility. Descriptive source-scoped facts do not require an installed version; procedures may. Never promise all events can be replayed. Source defaults do not establish installed settings. Use customer-safe summaries; never expose internal parameter names or paths in customer replies.'
 payload={'model':model,'store':False,'max_output_tokens':1800,'instructions':instructions,'input':[{'role':'user','content':json.dumps({'product':product,'version':version,'conversation':messages,'authorized_sandbox_guidance':model_sources(sources)},ensure_ascii=False)}],'text':{'format':{'type':'json_schema','name':'support_answer','strict':True,'schema':schema}}}
 request=Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
 try:
  with build_opener(NoRedirect(),ProxyHandler({})).open(request,timeout=45) as response:raw=response.read(1_000_001)
 except HTTPError as exc:
  labels={400:('model_request_error','The API rejected the model request or schema.'),401:('model_authentication_error','The API rejected authentication. Check the local OpenAI credential.'),403:('model_permission_error','The configured project does not have permission for this request.'),404:('model_not_found','The configured model or endpoint is unavailable to this project.'),429:('model_rate_or_quota_error','The API reports a rate or quota limit. Check project billing and limits.')}
  code,message=labels.get(exc.code,('model_api_error','The API returned an unsuccessful response.'))
  raise ModelUnavailable(message,code,True) from None
 except (TimeoutError,URLError):raise ModelUnavailable('The model connection timed out or could not reach the API.','model_connection_error',True) from None
 except Exception:raise ModelUnavailable('The model request failed. No support answer was generated.','model_api_error',True) from None
 try:
  if len(raw)>1_000_000:raise ValueError()
  result=json.loads(raw)
  if result.get('status')!='completed':raise ModelUnavailable('The model response was incomplete; no answer is displayed.','model_incomplete_response',True)
  parts=[p for item in result.get('output',[]) if item.get('type')=='message' for p in item.get('content',[])]
  if any(p.get('type')=='refusal' for p in parts):raise ModelUnavailable('The model declined the request.','model_refusal',True)
  output=''.join(p.get('text','') for p in parts if p.get('type')=='output_text');answer=json.loads(output)
  if set(answer)!={'answer','source_ids','needs_human'} or not isinstance(answer['answer'],str) or len(answer['answer'])>2500 or type(answer['needs_human']) is not bool:raise ValueError()
  valid={s['id'] for s in sources}
  if not isinstance(answer['source_ids'],list) or not answer['source_ids'] or any(not isinstance(i,str) or i not in valid for i in answer['source_ids']):raise ValueError()
  return answer
 except ModelUnavailable:raise
 except Exception:raise ModelUnavailable('The model returned an invalid answer or unsupported citation; no answer is displayed.','model_validation_error',True) from None
