"""Provider-neutral workflow evidence. Facts are reported, never verified diagnoses.

Private notes can select internal review work but never supply customer wording.
No ticket IDs, customer names, network calls, or technical repair instructions.
"""
import re
from datetime import datetime, timezone
from workflow_reply import draft as draft_workflow


def clean(body):
    return re.split(r'(?im)^\s*(?:_{5,}|On .+wrote:|From:|>).*', body)[0].strip()


def substantive(body):
    # Ignore a CC-only first paragraph even when followed by a long signature.
    first = re.split(r'\n\s*\n', body.strip(), maxsplit=1)[0].strip()
    if re.fullmatch(r'(?is)(?:adding|added|ccing|copying)\s+[^.!?\n]{1,100}(?:\s+(?:for visibility|for vision|to (?:this|the) thread))?[.!]?', first) and not re.search(r'(?i)\b(?:please|schedule|call|instead|configure|cancel)\b', body):
        return False
    return bool(body) and not re.fullmatch(
        r'(?is)(?:(?:adding|added|add|cc|ccing|copied|copying)\b.{0,120}|'
        r'(?:this )?ticket.*(?:merged|merge).*|merged (?:from|into).*|thanks[.!]?)', body)


def summarize(ticket):
    def stamp(c):
        try:
            value = datetime.fromisoformat(c.created_at.replace('Z', '+00:00'))
            return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()
        except ValueError:
            return float('-inf')

    records = [('Ticket description', clean(ticket.subject+'\n'+ticket.description), False)]
    records += [(f'Conversation {i}', clean(c.body), c.private)
                for i, c in sorted(enumerate(ticket.conversations, 1), key=lambda p: stamp(p[1]))
                if substantive(clean(c.body))]
    public = [(ref, body) for ref, body, private in records if not private]
    text = '\n'.join(body for _, body in public)
    internal = '\n'.join(body for _, body, _ in records)
    has = lambda pattern, value=text: bool(re.search(pattern, value, re.I | re.S))
    state = dict(workflow='', requested_outcome='', current_impact='Not established',
                 completed_actions=[], outstanding_work=[], action_owner='Human review',
                 evidence=[ref for ref, _ in public], latest_substantive_source=public[-1][0],
                 urgent=False, reply='', internal_evidence=[ref for ref, _, private in records if private])
    # An explicit later restoration supersedes an earlier outage signal.
    impact = None
    for ref, body in public:
        if has(r'out of service|cannot (?:scan|upload)|(?:lot|site|system).{0,45}(?:offline|down)|offline for (?:months|weeks)', body):
            impact = ('Reported operational outage; restoration unconfirmed', ref, True)
        if has(r'(?:vehicle|lot|site|system).{0,30}(?:back in service|fully restored|operating normally)', body):
            impact = ('Reported restored; support verification pending', ref, False)
    if impact:
        state.update(current_impact=impact[0], impact_source=impact[1], urgent=impact[2])

    if has(r'\brma\b|replacement controllers') and has(r'programmed|configuration|configure'):
        contact = ''
        contact_source = ''
        for ref, body in public:
            # Only explicit public coordination directions qualify; never infer from CC/signatures.
            matches = list(re.finditer(r'\b(?:schedule with|coordinate with|contact)\s+([A-Z][a-z]{1,24}(?:\s+[A-Z][a-z]{1,24})?)\s+(?:from|at)\s+([A-Z][A-Za-z0-9&-]{1,24})\b', body))
            if matches:
                m = matches[-1]
                contact = m.group(1) + ' at ' + m.group(2)
                contact_source = ref
        remote = has(r'remote session')
        target = contact or 'the contact you designated'
        plan = ('coordinate the proposed remote configuration session with ' if remote else 'coordinate the configuration plan with ') + target
        reply = ('I’m sorry the replacement process has been delayed. ' if state['urgent'] else 'Thank you for the replacement-controller update. ')
        reply += ('The next step is for support to ' + plan + '. Before confirming whether another shipment is needed, support needs to establish whether the delivered controllers can be configured for the site. ')
        reply += 'A session time and restoration date require confirmation from support.' if remote else 'No shipment or completion date is confirmed by this draft.'
        state.update(workflow='RMA coordination', requested_outcome='Agree replacement/configuration plan',
                     remote_session_proposed=remote, prolonged_outage=has(r'offline.{0,30}(?:months|weeks)|(?:months|weeks).{0,30}offline'),
                     coordination_contact=contact, contact_source=contact_source,
                     outstanding_work=['Support should '+plan+'. Obtain the exact controller model and installed software version from the device holder or RMA record; verify configuration availability before selecting an approved procedure. No programming steps or shipment commitment are established.'],
                     reply=reply)
    elif has(r'intercom') and has(r'virtual loop'):
        state.update(workflow='Multiple service issues', requested_outcome='Resolve remaining lane and intercom issues',
                     outstanding_work=['Review physical-loop investigation with the local access-control technician and track intercom work separately.'],
                     reply='Thank you for the updates. The virtual-loop workaround and the remaining physical-loop investigation need to be tracked separately from the intercom issue. Support should coordinate the next review with the local access-control technician and provide a separate intercom update.')
        if has(r'entry.{0,80}(?:restored|working|resolved|back up|operating as intended)'):
            state['completed_actions'].append('Entry service reported restored')
            state['reply'] += ' Entry service was reported restored; that does not establish that the other issues are resolved.'
    elif has(r'(?:install|replacement).{0,60}(?:unsuccessful|failed|not successful)|(?:unsuccessful|failed).{0,60}(?:install|replacement)', internal):
        state.update(workflow='Repair follow-up', requested_outcome='Agree next diagnostic/repair plan',
                     outstanding_work=['Review the unsuccessful repair evidence internally and agree the next diagnostic/repair plan.'],
                     reply='Thank you for the repair updates. Support needs to review the work already attempted and confirm the next diagnostic and repair plan. The cause and any additional parts required have not been confirmed.')
    elif impact and impact[2]:
        state.update(workflow='Operational outage', requested_outcome='Restore operation and obtain investigation update',
                     outstanding_work=['Escalate current operational impact; obtain investigation status and verify restoration after any changes.'],
                     reply='You reported that operation is interrupted. This requires urgent review by the support incident lead. Support needs to provide an investigation update and confirm whether service has been restored after the recent work. The cause and restoration time are not yet confirmed.')
    elif has(r'site visit') and has(r'mapping|facilities|floors|aisles'):
        state.update(workflow='Scheduled visit preparation', requested_outcome='Confirm visit readiness',
                     outstanding_work=['Verify the visit date/status in the thread and confirm mapping information and IT availability before further coordination.'],
                     reply='Thank you for the site-visit coordination. The preparation items are the parking-layout and naming information and IT availability for connectivity. Support should verify the visit status against the date already agreed in this thread and confirm any remaining readiness items. This draft does not confirm a new appointment.')
    if state['workflow']:
        state['action_owner'] = 'Support'
        draft_workflow(state, public[-1][1])
        if state['urgent'] and state['workflow'] != 'Operational outage':
            state['reply'] += ' The reported operational outage also requires urgent incident-lead review; restoration has not been confirmed.'
    return state
