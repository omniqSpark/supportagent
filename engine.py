"""Deterministic advisory engine. No network, credentials, or ticket-system imports."""
import re
from datetime import date
from dataclasses import replace
from domain import Ticket
from conversation_review import review_conversation
from knowledge_policy import production_blockers, candidates as source_candidates
from reply_drafting import improve_reply
from case_state import summarize
from library_guidance import recommend as recommend_library
from approved_style import apply_style, PROFILE_ID
from current_issue import current_issue, missing_product_question
from customer_wording import refine
from support_policy import internal_record, completion_labels

CATEGORIES = {
    "LPR camera": ["lpr", "camera", "plate recognition", "plate read"],
    "Edge device": ["edge device", "edge unit", "edge appliance"],
    "Event delivery": ["event delivery", "webhook", "missing events", "events missing"],
    "Network": ["network", "connectivity", "packet loss", "switch", "dns"],
    "SFTP": ["sftp", "file transfer"],
    "Software": ["software", "application", "dashboard", "login", "report export"],
    "Hardware": ["hardware", "power supply", "disk", "fan", "physical damage"],
}
RISK = {
    "Security concern — security responder review required": ["security", "breach", "unauthorized", "ransomware", "compromised", "exposed credentials", "data leak"],
    "Sensitive public safety matter — duty manager review required": ["public safety", "police", "law enforcement", "watchlist", "amber alert", "emergency vehicle", "injury", "life safety"],
    "Urgent outage — incident lead review required": ["outage", "all lanes", "site down", "site is down", "entire site", "production stopped", "critical", "urgent", "cannot operate", "system down"],
}


def match(text, phrase):
    return bool(re.search(r"\b" + re.escape(phrase) + r"\b", text, re.I))


def approved(record, sandbox):
    try:
        return (record.get("approval") == ("sandbox" if sandbox else "production")
                and bool(record.get("approved_by")) and date.fromisoformat(record["valid_until"]) >= date.today())
    except (KeyError, ValueError, TypeError):
        return False


def analyze(ticket: Ticket, knowledge: list, coverage: list, source_catalog=None) -> dict:
    source_catalog = source_catalog or []
    text = "\n".join([ticket.subject, ticket.description] + [c.body for c in ticket.conversations])
    focus=current_issue(ticket)
    classification_text=focus['classification_text'] or text
    evidence = {cat: [p for p in phrases if match(classification_text, p)] for cat, phrases in CATEGORIES.items()}
    candidates = [cat for cat, hits in evidence.items() if hits]
    category = candidates[0] if len(candidates) == 1 else "Needs triage"
    context = review_conversation(ticket)
    state = summarize(ticket)
    if focus['explicit_focus']:
        state['workflow']=''
        context.update(planned_upgrade=False, intermittent_controller=False, waiting_for_customer=False, question='', action_owner='Support', next_action='Review the customer’s explicitly stated current issue.')
    context['case_state'] = state
    if state['workflow'] and ticket.history_complete:
        if category == 'Needs triage' or state['workflow'] == 'Scheduled visit preparation':
            category = state['workflow']
        context.update(action_owner=state['action_owner'], next_action=' '.join(state['outstanding_work']), waiting_for_customer=False)
    if context['planned_upgrade']:
        category = 'Planned upgrade'
    elif context['intermittent_controller']:
        category = 'Intermittent controller fault'
    # Security policy discussion alone is not evidence of an incident.
    reasons = [reason for reason, phrases in RISK.items() if any(match(text, p) for p in phrases if p != 'security')]
    urgent = bool(reasons) or ticket.priority == 4
    if state['urgent']:
        urgent = True
        reasons.append('Reported operational outage — incident lead must verify restoration and current impact')
    if context['security_review']:
        reasons.append('Detected executable needs security review; breach or outage not established')
    if context['conflict']:
        reasons.append('Potentially conflicting compatibility advice; support must reconcile hardware-specific guidance')
    if ticket.priority == 4:
        reasons.append("Ticket system reports urgent priority — incident lead review required")
    sandbox = ticket.source == "sample"
    sites = [r for r in coverage if approved(r, sandbox)
             and r["customer_id"] == ticket.customer_id and r["site_id"] == ticket.site_id]
    identity = sites[0] if sites else None
    questions = []
    if not identity:
        reasons.append("Customer/site pair has no approved coverage record" if ticket.customer_id and ticket.site_id else "Customer/site identity is incomplete")
    if category == "Needs triage":
        questions.append("Which component is failing, and what exact error or symptom do you see?")
        reasons.append("Multiple issue categories match" if candidates else "Insufficient evidence to classify the issue")
    articles = []
    blocked_sources = []
    for a in knowledge:
        if a.get('category') != category:
            continue
        if not approved(a, sandbox):
            continue
        blockers = [] if sandbox else production_blockers(a, ticket, source_catalog)
        if blockers:
            blocked_sources.append({'id':a.get('id'),'reasons':blockers})
        else:
            articles.append(a)
    if not articles:
        reasons.append("No current approved knowledge source for this issue")
    if not ticket.history_complete:
        reasons.append("Conversation history is incomplete; a person must review the full record")
    eligible = sorted([r for r in sites if category in r["skills"] and r.get("available") is True],
                      key=lambda r: (r.get("rank", 99), r["technician"]))
    technician = eligible[0] if eligible else None
    if not technician:
        reasons.append("No available technician with approved site coverage and matching skill")
    if not questions and context['question']:
        questions.append(context['question'])
    if not questions and urgent:
        questions.append("When did the incident start, including timezone, and is it still ongoing?")
    if not questions and articles:
        questions.append(articles[0]["question"])
    question = questions[0] if questions else "When did the issue start, including timezone?"
    support_action = context['action_owner'] == 'Support' and context['intermittent_controller'] and context['next_action'].startswith('Review the other lane') and not urgent and ticket.history_complete
    if support_action:
        question = 'No additional customer detail requested now; support review is the next step.'
    if context['waiting_for_customer'] and not urgent:
        question = 'Already requested in the latest support reply; await the customer response.'
    # No technical instructions during escalation. Questions are a single next step.
    advice = [] if reasons else [{"text": a["advice"], "source": a.get('source_id',a['id']), "version": a["version"], "locator":a.get('locator','Sandbox fixture')} for a in articles]
    priority = "Urgent" if urgent else "High" if ticket.priority == 3 or context['security_review'] else "Normal"
    reply = "Thank you for the upgrade-planning information. " if context['planned_upgrade'] else "Thank you for reporting this issue. "
    reply += "This needs review by a support specialist. " if reasons else "We can begin with a read-only check. "
    reply += question + " Please do not include passwords, keys, or sensitive personal data."
    if support_action:
        reply = ('Thank you for the update. ' +
                 ('You reported that the controllers remain online without another occurrence. ' if context['currently_stable'] else '') +
                 'Your request to compare the other lane controllers’ temperatures needs support review. The cause has not been confirmed. No further information is requested from you at this stage.')
    if context['waiting_for_customer'] and not urgent:
        reply = ('Thank you for contacting support. A remote session was requested in our previous reply. Please confirm a suitable time to coordinate the session with support. Do not send passwords or access codes in this ticket.' if context['remote_session_requested'] else
                 'Thank you for the information provided so far. We are awaiting the information requested in our latest reply before confirming the next steps.')
    if context['language'] == 'es':
        if urgent or not ticket.history_complete:
            reply = 'Gracias por contactarnos. Este caso necesita revisión por un especialista antes de confirmar los próximos pasos. No comparta contraseñas ni códigos de acceso en este ticket.'
        elif context['remote_session_requested'] and context['waiting_for_customer']:
            reply = 'Hola, gracias por contactarnos. En nuestra respuesta anterior solicitamos coordinar una sesión remota. Por favor, confirme un horario conveniente para organizarla con soporte. No envíe contraseñas ni códigos de acceso en este ticket.'
        else:
            reply = 'Gracias por la información. El equipo de soporte debe revisar su solicitud antes de confirmar los próximos pasos. No comparta contraseñas ni códigos de acceso en este ticket.'
    reply = improve_reply(ticket, context, reply, urgent, support_action)
    sensitive = any('Security concern' in r or 'public safety' in r for r in reasons) or context['security_review']
    if state['workflow'] and ticket.history_complete and not sensitive:
        reply = state['reply']
        if urgent and not state['urgent']:
            reply += ' Support must also review the urgent indicators in the record and confirm current impact.'
        question = 'Support review is next; no repeated intake question is needed.'
    if advice and context['language'] != 'es':
        reply += "\n\n" + "\n".join(f'{a["text"]} [{a["source"]} v{a["version"]}; {a["locator"]}]' for a in advice)
    customer = identity["customer"] if identity else ticket.customer_name or ticket.customer_id or "Unverified customer"
    site = identity["site"] if identity else ticket.site_name or ticket.site_id or "Unverified site"
    route = technician["technician"] if technician else "Human dispatch"
    handoff = (f"Ticket {ticket.id} • {customer} / {site}\n"
               f"Reported issue (unverified): {ticket.subject}\n{ticket.description[:1200]}\n"
               f"Current ticket owner: {ticket.assigned_agent or 'Not resolved'}. {ticket.mapping_notes}\n"
               f"Classification: {category}; candidates: {', '.join(candidates) or 'none'}. Priority: {priority}.\n"
               f"Recommended local resource: {route}. Dispatch and availability require human confirmation.\n"
               f"Evidence terms: {', '.join(p for hits in evidence.values() for p in hits) or 'none'}. "
               f"Reviewed {len(ticket.conversations)} conversations, including internal notes. Diagnosis unconfirmed.\n"
               f"Escalation: {'; '.join(reasons) or 'No mandatory escalation detected; human review still required'}.\n"
               f"Next detail: {question}\nSources: {', '.join(a['id'] + ' v' + a['version'] for a in articles) or 'none'}.")
    if ticket.identity_evidence:
        handoff += '\nAccount lookup: ' + ticket.identity_evidence.get('status', '')
        handoff += '\nAccount candidates: ' + '; '.join(c['name'] + ' (' + ', '.join(c['evidence']) + ')' for c in ticket.identity_evidence.get('company_candidates', []))
        handoff += '\nIdentity checks for support: ' + ' '.join(ticket.identity_evidence.get('warnings', []))
    if context['pending']:
        handoff += '\nItems to verify:\n' + '\n'.join(p['topic']+' ['+p['source']+']' for p in context['pending'])
    if context['conflict_sources']:
        handoff += '\nConflicting guidance evidence: ' + '; '.join(context['conflict_sources'])
    handoff += '\nNext action owner: ' + context['action_owner'] + '. ' + context['next_action']
    if state['workflow']:
        handoff += ('\nRequested outcome: ' + state['requested_outcome'] +
                    '\nCurrent impact: ' + state['current_impact'] +
                    '\nCompleted/reported: ' + ('; '.join(state['completed_actions']) or 'Review evidence before confirming completion') +
                    '\nLatest substantive public evidence: ' + state['latest_substantive_source'] +
                    '\nInternal review evidence: ' + (', '.join(state['internal_evidence']) or 'none'))
    guidance_ticket=replace(ticket, subject='', description=focus['classification_text'], conversations=[]) if focus['explicit_focus'] else ticket
    library = recommend_library(guidance_ticket, urgent=urgent or sensitive, waiting=context['waiting_for_customer'])
    if library['customer']:
        item = library['customer'][0]
        question = item['text']
        reply = 'Thank you for reporting this issue. ' + item['text']
        handoff += '\nCustomer draft question: ' + question + ' [' + item['citation'] + ']'
    for item in library['technician']:
        handoff += '\nTechnician suggestion: ' + item['text'] + ' [' + item['citation'] + ']'
    product_question=missing_product_question(ticket,library['withheld'],focus)
    if product_question and not urgent and not sensitive and ticket.history_complete and not state['workflow'] and not support_action and not context['waiting_for_customer'] and not advice and not library['customer']:
        question=product_question
        reply='Thanks for the update. '+question
    before_style = reply
    reply = apply_style(reply, protected=bool(advice) or sensitive or not ticket.history_complete or context['language'] != 'en')
    prior_question=question
    reply,question=refine(ticket,reply,question,urgent=urgent,protected=bool(advice) or not ticket.history_complete or context['language']!='en',context=context)
    if prior_question!=question:
        handoff=handoff.replace(prior_question,question)
    record_sources=articles+library['customer']+library['technician']
    record=internal_record(ticket.product_model,ticket.product_version,record_sources,
        context['next_action'] or question,[question] if '?' in question else [],reasons,
        state['completed_actions']+completion_labels(focus['classification_text']),
        'Read-only ticket draft; human approval required')
    return dict(internal_record=record, current_issue=focus, reply_before_style=before_style, style_profile=PROFILE_ID, style_changed=reply != before_style, library_guidance=library, category=category, candidates=candidates, evidence=evidence, priority=priority,
                confidence="Intermittent controller symptoms reported; cause unconfirmed" if context['intermittent_controller'] else "Upgrade-planning language in original request; human review required" if context['planned_upgrade'] else "Single-category rule match; diagnosis unconfirmed" if len(candidates) == 1 else "Low — human triage",
                conversation_review=context,
                candidate_sources=source_candidates(ticket,source_catalog), blocked_sources=blocked_sources,
                reply_language=context['language'], send_recommendation='Hold — customer response already requested' if context['waiting_for_customer'] else 'Human approval required; draft only',
                customer=customer, site=site, technician=route,
                routing_reason=(f"Exact customer/site match; {category} skill; available in coverage table; rank {technician['rank']}."
                                if technician else "Abstained: identity, coverage, availability, or skill could not be verified."),
                escalation_reasons=reasons, escalate=bool(reasons), question=question, advice=advice,
                reply=reply, handoff=handoff, sources=articles,
                coverage_source=technician.get("id") if technician else None)
