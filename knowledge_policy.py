"""Production advice requires an explicit, version-scoped review decision."""
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
import hashlib


def production_blockers(article, ticket, catalog):
    sources=[s for s in catalog if s.get('id') == article.get('source_id')]
    if len(sources) != 1:
        return ['Missing or ambiguous source register entry']
    source=sources[0];reasons=[]
    if source.get('kind') == 'local':
        try:
            if hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() != source.get('sha256'):
                reasons.append('Original source has changed since registration')
        except (OSError,KeyError):
            reasons.append('Original source cannot be verified')
    elif source.get('kind') == 'freshdesk':
        try:
            retrieved=datetime.fromisoformat(source['retrieved_at'])
            age=datetime.now(timezone.utc)-retrieved
            if age > timedelta(days=7) or age < timedelta(0):
                reasons.append('Source snapshot must be refreshed (maximum age seven days)')
        except (KeyError,ValueError,TypeError):
            reasons.append('Source retrieval date is missing or invalid')
    else:
        reasons.append('Source provenance type is unsupported')
    if source.get('approval') != 'production' or not source.get('approved_by'):
        reasons.append('Source is awaiting production approval')
    if not article.get('approved_source_sha256') or article['approved_source_sha256'] != source.get('sha256'):
        reasons.append('Approved source revision does not match the registered revision')
    if article.get('customer_safe') is not True:
        reasons.append('Customer distribution has not been approved')
    if not article.get('locator'):
        reasons.append('Missing page, section, or article passage citation')
    if not ticket.product_model or ticket.product_model not in article.get('models',[]):
        reasons.append('Deployed model is missing or not covered')
    if not ticket.product_version or ticket.product_version not in article.get('product_versions',[]):
        reasons.append('Deployed version is missing or not covered')
    try:
        if date.fromisoformat(source.get('valid_until','')) < date.today():
            reasons.append('Source approval expired')
    except (ValueError,TypeError):
        reasons.append('Source approval expiry is missing')
    return reasons


def candidates(ticket, catalog):
    text='\n'.join([ticket.subject,ticket.description]+[c.body for c in ticket.conversations])
    result=[]
    for source in catalog:
        matches=[term for term in source.get('match_terms',[]) if re.search(r'\b'+re.escape(term)+r'\b',text,re.I)]
        if matches:
            result.append({**source,'matched_terms':matches,'use_status':'Candidate reference — relevance is not approval or deployed-version compatibility'})
    return result
