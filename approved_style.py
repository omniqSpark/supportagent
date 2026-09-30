"""Bounded editorial rules for concise sandbox replies.

No historical names, technical claims, signatures, or commitments are reused.
Source-backed instructions and urgent/incomplete reviews retain original wording.
"""

PROFILE_ID = 'reviewed-style-v2-concise'
EXAMPLE_IDS = ()  # Private training records are not distributed.


def apply_style(reply, *, protected=False):
    if protected:
        return reply
    replacements = (
        ('Thank you for the repair updates. Support needs to review the work already attempted with the technician and confirm the next diagnostic and repair plan before recommending more parts. The cause has not yet been confirmed.',
         'Thanks for the update. Our next step is to review the work completed with the technician and confirm the diagnostic and repair plan before recommending additional parts. The cause is still unconfirmed.'),
        ('The next step is to coordinate the remote session requested in our previous reply. A suitable time still needs to be confirmed; the reviewed information does not establish that the session has taken place. ',
         'Please confirm a suitable time for the remote session requested in our previous reply. '),
        ('Thank you for the information provided so far. We are awaiting the information requested in our latest reply before confirming the next steps.',
         'Thanks for the update. Please send the details requested in our last reply so we can confirm the next step.'),
        ('Your request to compare the other lane controllersÃ¢â‚¬â„¢ temperatures needs support review.',
         'Support needs to compare the other lane controllersÃ¢â‚¬â„¢ temperatures.'),
        ('That comparison is still pending, and the cause has not been confirmed.',
         'The comparison is pending; the cause has not been confirmed.'),
        ('A session time and restoration estimate still need to be confirmed.',
         'Session timing and restoration remain unconfirmed.'),
        ('The configuration approach and any further shipment still need to be confirmed.',
         'Configuration and any further shipment remain unconfirmed.'),
        ('Thank you for the update. ', 'Thanks for the update. '),
        ('Thank you for explaining your request', 'Thanks for explaining your request'),
        ('Thank you for reporting this issue. ', 'Thanks for letting us know. '),
        ('Thank you for the updates. ', 'Thanks for the update. '),
        ('Thank you for the repair updates. ', 'Thanks for the repair update. '),
        ('Thank you for the replacement-controller update. ', 'Thanks for the controller update. '),
        ('Thank you for coordinating the site visit. ', 'Thanks for coordinating the visit. '),
        ('This needs review by a support specialist. ', 'A support specialist needs to review this. '),
        ('The next step is for support to ', 'Support needs to '),
        ('The preparation items already discussed are ', 'The visit needs '),
        ('along with IT availability for connectivity', 'with IT available for connectivity'),
        ('before confirming the arrangements', 'before confirming the visit'),
        ('The cause has not yet been confirmed.', 'The cause is still unconfirmed.'),
        ('The cause and any additional parts required have not been confirmed.', 'The cause and required parts are still unconfirmed.'),
        ('No further information is requested from you at this stage.', 'No further details are needed from you right now.'),
        ('Please do not include passwords, keys, or sensitive personal data.', 'Please omit passwords, keys and sensitive personal data.'),
    )
    for old,new in replacements:
        reply=reply.replace(old,new)
    return reply
