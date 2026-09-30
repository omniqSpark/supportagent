"""Narrow chronology rules; explicit customer updates, never inferred diagnosis."""
import re
from datetime import datetime
from case_state import clean, substantive


def current_issue(ticket):
    records=[]
    for index,c in enumerate(ticket.conversations,1):
        if c.private or c.author_role!='customer' or not substantive(clean(c.body)):
            continue
        try:
            stamp=datetime.fromisoformat(c.created_at.replace('Z','+00:00'))
            if stamp.tzinfo is None:continue
        except ValueError:continue
        records.append((stamp,index,clean(c.body)))
    if not records:
        return {'text':clean(ticket.subject+'\n'+ticket.description)[:500], 'source':'Ticket description', 'explicit_focus':False,'classification_text':''}
    _,index,body=max(records,key=lambda r:r[0])
    # Only an explicit statement of the remaining/sole issue narrows classification.
    match=re.search(r'(?im)\b(?:the )?(?:only remaining issue|remaining issue|current issue)\s*(?:is|:)\s*([^\n]+)',body)
    return {'text':body[:500], 'source':f'Conversation {index}',
            'explicit_focus':bool(match and ticket.history_complete),
            'classification_text':match.group(1) if match and ticket.history_complete else ''}


def missing_product_question(ticket, withheld, issue):
    if not withheld:return None
    # Avoid repeating a product request if explicit product/version details are in public text.
    public='\n'.join([ticket.description]+[c.body for c in ticket.conversations if not c.private])
    if not ticket.product_model and any('Confirm product model:' in x['reason'] for x in withheld):
        if re.search(r'(?i)\b(?:QN\s*\d+|SeeControl|Controller Application|Dynamic REST Publisher)\b',public):return None
        return 'Which product model is affected?'
    if ticket.product_model and not ticket.product_version and any('Confirm deployed version:' in x['reason'] for x in withheld):
        if re.search(r'(?i)\b(?:version|build|v)\s*\d+(?:\.\d+)+',public):return None
        return 'Which software version is installed?'
    return None
