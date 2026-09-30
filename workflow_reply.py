"""Human-readable coordination drafts. No product procedures or automatic sending.

Coordination wording remains advisory and requires human review.
Names, dates and device identities are never copied from that example.
"""
import re


def draft(state, latest_public):
    workflow = state['workflow']
    if not workflow:
        return
    latest = latest_public.lower()
    if re.search(r'\b(cancelled|canceled|postponed|rescheduled)\b', latest):
        state['reply'] = ('Thank you for the update. Support needs to review the changed arrangements and confirm the next step before making another booking or shipment commitment.')
        state['outstanding_work'] = ['Review the changed arrangements in the latest public message; confirm which prior plan remains valid.']
        return
    if workflow == 'RMA coordination':
        if re.search(r'\b(?:configuration|remote session).{0,40}(?:completed|finished|successful)\b',latest):
            state['reply'] = ('Thank you for the configuration update. Support needs to confirm the outcome and whether operation has been restored before arranging further work or another shipment.')
            state['outstanding_work'] = ['Verify the reported configuration outcome and current operation; do not repeat a completed-session request.']
            return
        contact = state.get('coordination_contact') or 'the contact you designated'
        remote = state.get('remote_session_proposed', False)
        opening = ('I’m sorry the site has been unavailable for so long. ' if state.get('prolonged_outage') and state['urgent']
                   else 'I’m sorry operation has been interrupted. ' if state['urgent']
                   else 'Thank you for the replacement-controller update. ')
        state['reply'] = (opening + 'The next step is for support to coordinate ' +
                          ('the proposed remote configuration session' if remote else 'the configuration plan') +
                          ' with ' + contact + ' and check whether the units already delivered can be configured for the site before confirming another shipment. ' +
                          ('A session time and restoration estimate still need to be confirmed.' if remote else 'The configuration approach and any further shipment still need to be confirmed.'))
    elif workflow == 'Repair follow-up':
        state['reply'] = ('Thank you for the repair updates. Support needs to review the work already attempted with the technician and confirm the next diagnostic and repair plan before recommending more parts. The cause has not yet been confirmed.')
    elif workflow == 'Multiple service issues':
        opening = 'Thank you for confirming that the entry gates are working again. ' if state['completed_actions'] else 'Thank you for the updates. '
        state['reply'] = (opening + 'The remaining work is to investigate the physical loop with the local access-control technician and provide a separate intercom update. The virtual-loop workaround does not establish that the underlying issue is resolved.')
    elif workflow == 'Scheduled visit preparation':
        state['reply'] = ('Thank you for coordinating the site visit. The preparation items already discussed are the parking layout and naming information, along with IT availability for connectivity. Support should verify the visit status and any outstanding readiness items before confirming the arrangements.')
    elif workflow == 'Operational outage':
        state['reply'] = ('I’m sorry operation is interrupted. Support needs to obtain an investigation update and confirm the outcome of the recent work. This requires urgent review while service remains unavailable; the cause and restoration time have not yet been confirmed.')
