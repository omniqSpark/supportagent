"""Explicitly authorized local draft cards; never production article approvals."""
import hashlib
import json
import re
from pathlib import Path
from case_state import clean
from support_policy import repeat_block

ROOT = Path(__file__).parent / 'library-review'
AUTHORIZED = frozenset(('G01', 'G02', 'G03', 'G04', 'G05', 'G06'))


def recommend(ticket, urgent=False, waiting=False):
    result = dict(customer=[], technician=[], withheld=[], scope='Local sandbox drafts only; human approval required')
    try:
        cards = json.loads((ROOT / 'proposed_guidance.json').read_text(encoding='utf-8'))
        inventory = {r['source_id']: r for r in json.loads((ROOT / 'source_inventory.json').read_text(encoding='utf-8'))}
    except (OSError, ValueError, KeyError):
        result['withheld'].append(dict(id='library', reason='Review library unavailable'))
        return result
    public = '\n'.join([clean(ticket.subject), clean(ticket.description)] +
                       [clean(c.body) for c in ticket.conversations if not c.private])
    text = public.lower()
    def match(pattern):
        return bool(re.search(pattern, text))
    blurry = match(r'blurr|out of focus|image sharpness')
    rename = match(r'renam|computer.name chang|configuration.upload|format\.ini')
    triggers = {
        'G01': match(r'physical damage|broken|damaged|will not power|no power'),
        'G02': blurry,
        'G03': rename,
        'G04': match(r'controller') and match(r'fault|error|crash|offline|log'),
        'G05': match(r'missing events|event delivery|backlog|events missing'),
        'G06': rename,
    }
    scopes = {'G01': ('QN33', None), 'G02': ('QN33', None),
              'G03': ('SeeControl', '5.1'), 'G04': ('Controller Application', '5.1'),
              'G05': ('Dynamic REST Publisher', None), 'G06': ('SeeControl', '5.1')}
    for card in cards:
        cid = card['id']
        if cid not in AUTHORIZED or not triggers[cid]:
            continue
        reason = ''
        model, version = scopes[cid]
        if not ticket.history_complete:
            reason = 'Complete history required before recommending guidance'
        elif ticket.product_model.casefold() != model.casefold():
            reason = 'Confirm product model: ' + model
        elif version and ticket.product_version != version:
            reason = 'Confirm deployed version: ' + version
        elif cid == 'G05' and not ticket.product_version:
            reason = 'Confirm deployed extension build and document applicability'
        if cid == 'G05' and not reason:
            reason = 'Extension build applicability remains unapproved; document does not establish supported builds'
        try:
            source = inventory[card['source_id']]
            if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() != card['source_sha256']:
                reason = 'Source changed since passage review'
        except (OSError, KeyError):
            reason = 'Original source cannot be verified'
        if card['proposed_audience'] == 'Customer':
            if urgent:
                reason = 'Urgent/security/public-safety review takes precedence over routine questions'
            elif waiting:
                reason = 'Await existing customer request; do not repeat intake'
            elif cid == 'G02' and match(r'(?:both|live video|captured.{0,15}image).{0,45}(?:blurr|out of focus)|(?:blurr|out of focus).{0,45}(?:both|live video|captured.{0,15}image)'):
                reason = 'Image location already supplied; technician should review the reported observation'
            elif cid == 'G03' and match(r'(?:after|since|following).{0,45}(?:renam|name chang)|(?:not|never).{0,20}renam'):
                reason = 'Rename history already supplied; do not repeat the question'
        if urgent:
            reason = 'Urgent/security/public-safety review takes precedence over routine guidance'
        if repeat_block(public,[{'id':cid}]):
            reason = 'This check was already reported attempted; a technician must review its outcome before choosing a further documented step'
        if reason:
            result['withheld'].append(dict(id=cid, reason=reason))
            continue
        item = dict(id=cid, title=card['title'], text=card['proposed_guidance'].replace(' If the ticket already answers this, do not ask again.',''),
                    citation=f"{card['source_id']}, PDF p. {card['pdf_page']}",
                    filename=source['filename'], applicability=card['applicability'],
                    limitations=card['blockers'], approval='User-authorized sandbox evaluation only')
        result['customer' if card['proposed_audience'] == 'Customer' else 'technician'].append(item)
    result['customer'] = result['customer'][:1]
    return result
