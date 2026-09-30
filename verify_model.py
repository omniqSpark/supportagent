"""Explicit live smoke test. Never prints keys or loads customer tickets."""
import argparse,json
from connectors import load_env
from chat_model import status,ModelUnavailable
from chat_service import chat

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args();load_env()
 config=status();print(json.dumps(config,indent=2))
 if not args.live:
  print('Configuration check only. Add --live to send one fictional replay question with reviewed excerpts.');return
 if not config['ready']:
  print('BLOCKED: real model mode is not configured. No network request made.');raise SystemExit(2)
 try:
  result=chat(dict(scope='fictional',message='Can all missing events be replayed?',product='Dynamic REST Publisher',version='',audience='customer'))
 except ModelUnavailable as error:
  print(json.dumps({'response_kind':error.code,'error':str(error),'attempted':error.attempted},indent=2));raise SystemExit(1)
 print(json.dumps({k:result[k] for k in ('response_kind','mode','answer','trace')},indent=2))
 if result['response_kind']!='generated_answer':raise SystemExit(1)
if __name__=='__main__':main()
