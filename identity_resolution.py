"""Explain identity evidence without treating senders as service sites."""


def resolve(ticket_company, contact, directory, site):
    companies={str(c['id']):c for c in directory}
    linked=set()
    if contact.get('company_id'):linked.add(str(contact['company_id']))
    for item in contact.get('other_companies') or []:
        value=item.get('company_id') if isinstance(item,dict) else item
        if value:linked.add(str(value))
    email=contact.get('email') or ''
    domain=email.rsplit('@',1)[-1].lower().strip() if '@' in email else ''
    internal=domain=='omniq.com' or domain.endswith('.omniq.com')
    candidates=[]
    for cid,c in companies.items():
        basis=[]
        if cid in linked:basis.append('Explicit requester-contact company association')
        for configured in c.get('domains') or []:
            configured=configured.lower().strip()
            if domain and domain==configured:basis.append('Exact email-domain match')
            elif configured and domain.endswith('.'+configured):basis.append('Email subdomain candidate; not a verified account mapping')
        if basis:candidates.append({'id':cid,'name':c.get('name',''),'evidence':basis})
    ticket_company=str(ticket_company or '')
    warnings=[]
    if not directory:warnings.append('Company directory unavailable; domain candidates could not be checked.')
    if internal:warnings.append('Internal omniQ requester: identify the represented customer from the case; do not route as an omniQ customer automatically.')
    if len(linked)>1:warnings.append('Requester is associated with multiple companies; service account requires confirmation.')
    if ticket_company and linked and ticket_company not in linked:warnings.append('Ticket company and requester company differ; do not overwrite either.')
    if not site:warnings.append('Service location is not recorded in the mapped site field; email does not identify a site.')
    if not ticket_company:warnings.append('Canonical service account is unresolved; candidates require internal confirmation.')
    warnings.append('Requester organization may be a partner or intermediary. Company evidence does not establish site coverage, technician assignment or product applicability.')
    return {'ticket_company_id':ticket_company,'requester_company_ids':sorted(linked),
            'requester_domain':domain,'internal_requester':internal,'company_candidates':candidates,
            'site_recorded':bool(site),'status':'Ticket company recorded; service scope still needs coverage validation' if ticket_company else 'Internal account review required',
            'warnings':warnings,'directory_basis':'Local read-only directory snapshot; candidate evidence, not approved mapping'}


def apply_display_confirmation(ticket_id, evidence, current_name):
    """No customer-specific overrides are distributed in the public sandbox."""
    return current_name
