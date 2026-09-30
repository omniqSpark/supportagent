"""Customer wording refinements authorized by the 12-ticket human review.
No inferred titles, diagnosis, appointments or technical procedures.
"""
import re
from case_state import clean


def refine(ticket, reply, question, *, urgent=False, protected=False, context=None):
    context=context or {}
    public='\n'.join([clean(ticket.subject),clean(ticket.description)]+[clean(c.body) for c in ticket.conversations if not c.private])
    reminder_free=reply.replace('Please do not include passwords, keys, or sensitive personal data.','').replace('Please omit passwords, keys and sensitive personal data.','')
    credentials=bool(context.get('remote_session_requested') or re.search(r'(?i)\b(password|credentials?|api.?key|access code|teamviewer|anydesk|remote access|remote session)\b',ticket.subject+' '+reminder_free))
    if ticket.history_complete and not urgent and not credentials:
        for warning in (' Please do not include passwords, keys, or sensitive personal data.', ' Please omit passwords, keys and sensitive personal data.'):
            reply=reply.replace(warning,'')
    if not protected:
        for old,new in [('When did the issue start, including timezone?', 'When did the issue start?'),('When did the incident start, including timezone, and is it still ongoing?', 'When did the incident start, and is it still ongoing?')]:
            reply=reply.replace(old,new)
            question=question.replace(old,new)
        # Replace only generic intake, never an existing workflow or source-backed procedure.
        generic=('Which component is failing' in reply or 'When did the issue start?' in reply)
        if generic and not urgent and ticket.history_complete and not context.get('waiting_for_customer'):
            if re.search(r'(?i)upload.{0,30}photos|photo.{0,20}upload',public) and re.search(r'(?i)schedule.{0,30}meeting|meeting.{0,30}look into',public):
                reply='Thanks for letting us know about the photo upload issue. Support needs to confirm a time to review it with you.'
                question='Support to confirm session availability; no additional customer detail requested.'
            elif re.search(r'(?i)dashboard',public) and re.search(r'(?i)permits.{0,30}vehicles|vehicles.{0,30}permits',public):
                reply='Thanks for reporting the missing dashboard tabs. Support needs to review access to the permits and vehicles tabs before recommending changes.'
                question='Support to review the reported missing dashboard tabs; no additional customer detail requested.'
            elif re.search(r'(?i)e-?cite',ticket.subject):
                reply='Thanks for reporting the eCite issue. Support needs to review the vehicle details and the troubleshooting already recorded before recommending the next step.'
                question='Support to review the recorded eCite symptoms and troubleshooting; no repeated intake question.'
    name=ticket.requester_name.strip()
    # Use the contact record as written; do not parse signatures or infer gender/titles.
    if (name and len(name)<=70 and re.fullmatch(r"[^\W\d_][^\d\n\r<>@{}:;!?=]{0,69}",name,re.UNICODE)
            and not ticket.identity_evidence.get('internal_requester')
            and not re.search(r'(?i)\b(mr|mrs|ms|dr)\.?\s',name)
            and not re.search(r'(?i)\b(support|admin|team|operations|department|company|unknown|no.?reply|test)\b',name)):
        reply='Hi '+name+',\n\n'+reply
    return reply,question
