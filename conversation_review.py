"""Conservative conversation signals, not a diagnosis or an approval source."""
import re
from datetime import datetime, timezone


def review_conversation(ticket):
    def timestamp(c):
        try:
            dt = datetime.fromisoformat(c.created_at.replace('Z', '+00:00'))
            return dt.replace(tzinfo=timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp()
        except ValueError:
            return float('-inf')

    entries = sorted(enumerate(ticket.conversations, 1), key=lambda pair: timestamp(pair[1]))
    # Remove quoted email tails; retain original entry numbers for provenance.
    records = [('Ticket description', ticket.subject + '\n' + ticket.description)]
    records += [(f'Conversation {i} ({c.created_at or "date unknown"})', re.split(r'(?m)^\s*(?:_{5,}|On .+wrote:|>).*', c.body)[0]) for i,c in entries]
    initial = records[0][1]
    planned = bool(re.search(r'(?i)\b(upgrad\w*|migrat\w*|replac\w*)\b', initial) and re.search(r'(?i)windows\s*11', initial))
    security = [ref for ref,body in records if re.search(r'(?i)(?:detect\w*|suspicious|legitimate).{0,180}\.exe|\.exe.{0,180}(?:legitimate|suspicious)|malware alert', body)]
    positive, negative, requests = [], [], []
    for ref,body in records:
        if re.search(r'(?i)(?:cpu|processor).{0,80}(?:is compatible)|(?:current|existing).{0,80}(?:version|software).{0,80}(?:should still run|will work)|can definitely image', body):
            positive.append(ref)
        if re.search(r'(?i)(?:older|existing|these).{0,100}(?:do not|does not|don.t|may not|cannot).{0,60}(?:support|upgrade)', body):
            negative.append(ref)
        if re.search(r'(?i)(?:can we get|please (?:send|confirm|provide)|need).{0,70}(?:specs|specifications|server models|hardware model)', body):
            requests.append((ref,body))
    conflict = planned and bool(positive and negative)
    latest = records[-1][0]
    pending = []
    if planned and requests and requests[-1][0] == latest:
        pending.append({'topic':'Server model and specifications requested in latest message', 'source':latest})
    if security:
        pending.append({'topic':'Detected executable legitimacy needs security review; resolution not verified', 'source':security[-1]})
    if planned:
        for topic,pattern in [('Firewall ports and protocols',r'ports.{0,80}(?:firewall|protocol)|network requirements'),('Hardware lifecycle',r'hardware lifecycle'),('Inventory and support estimate',r'list of the servers|estimate on how much time')]:
            refs=[ref for ref,body in records if re.search(pattern,body,re.I)]
            if refs: pending.append({'topic':topic+' — verify whether answered', 'source':refs[-1]})
    question = ''
    if planned and (conflict or (pending and pending[0]['source'] == latest and requests)):
        question = 'Please confirm each controller’s manufacturer/model and specifications so support can verify the upgrade path.'
    elif planned:
        question = 'Please confirm which upgrade-planning question remains unresolved after the latest support response.'
    intermittent = bool(re.search(r'(?i)\bcontrollers?\b', initial) and re.search(r'(?i)dropp?\w* offline|intermittent|restart.{0,40}controller', initial))
    public = [(ref,body) for (ref,body),(_,c) in zip(records[1:],entries) if not c.private]
    latest_public = public[-1] if public else ('Ticket description',initial)
    public_entries = [(ref,body,c) for (ref,body),(_,c) in zip(records[1:],entries) if not c.private]
    latest_role = public_entries[-1][2].author_role if public_entries else 'unknown'
    customer_text = '\n'.join([initial] + [body for ref,body,c in public_entries if c.author_role == 'customer'])
    language = 'es' if len(re.findall(r'(?i)\b(hola|gracias|necesito|soporte|cámara|configurar|saludos|problema)\b',customer_text)) >= 3 else 'en'
    action_owner, next_action = 'Human review', ''
    stable = intermittent and bool(re.search(r'(?i)(?:still|both).{0,50}(?:up and online|online).{0,100}(?:not had|no further|no more)|no further occurrences',latest_public[1]))
    comparison = intermittent and bool(re.search(r'(?i)(?:can you|please).{0,60}(?:check|compare).{0,100}(?:other|remaining).{0,100}(?:temperature|controllers)',latest_public[1]))
    if comparison and latest_role != 'support':
        action_owner = 'Support'
        next_action = 'Review the other lane controllers and compare their reported temperatures; document findings before drawing a conclusion about the cause.'
        pending.append({'topic':next_action,'source':latest_public[0]})
    elif intermittent and latest_role != 'customer' and re.search(r'(?i)(?:please|could you|can you).{0,50}(?:send|provide|confirm).{0,60}(?:time|timestamp|details|logs)',latest_public[1]):
        action_owner = 'Customer'
        next_action = 'Customer response requested in the latest public message; confirm receipt before repeating the request.'
    if comparison:
        question = ''
    remote_request = latest_role == 'support' and bool(re.search(r'(?i)teamviewer|remote access|acceso remoto',latest_public[1])) and bool(re.search(r'(?i)\?|please|could you|podr[ií]a|provide|confirm',latest_public[1]))
    response_needed = latest_role == 'support' and bool(re.search(r'(?i)(?:can we get|please (?:send|provide|confirm)|could you).{0,100}(?:specs|specifications|model|details|logs|timestamp)',latest_public[1]))
    waiting = remote_request or response_needed
    if waiting:
        action_owner = 'Customer'
        next_action = ('Await availability for a support-coordinated remote session; do not request passwords in the ticket.' if remote_request else 'Await the information requested in the latest support reply; do not duplicate the request.')
        pending.append({'topic':next_action,'source':latest_public[0]})
    elif latest_role == 'customer' and action_owner == 'Human review':
        action_owner = 'Support'
        next_action = 'Review the latest customer response before requesting further information.'
    if not ticket.history_complete:
        action_owner = 'Human review'
        next_action = 'Review the complete conversation history before deciding who should act next.'
        waiting = False
    return dict(planned_upgrade=planned, security_review=bool(security), conflict=conflict,
                language=language, waiting_for_customer=waiting, remote_session_requested=remote_request,
                latest_public_source=latest_public[0], latest_public_role=latest_role,
                intermittent_controller=intermittent, currently_stable=stable,
                action_owner=action_owner, next_action=next_action,
                conflict_sources=positive+negative if conflict else [], pending=pending,
                question=question, latest_source=latest)
