"""Bounded, evidence-conditioned reply wording. No diagnosis or action execution."""
import re


def improve_reply(ticket, context, fallback, urgent, support_action):
    if urgent or not ticket.history_complete:
        return fallback
    public_text='\n'.join([ticket.subject,ticket.description]+[c.body for c in ticket.conversations if not c.private])
    if context['planned_upgrade'] and context['waiting_for_customer']:
        reply=('Thank you for the details about the proposed Windows 11 upgrade. '
               'The controller manufacturer/model and specifications requested in our last reply are still needed to verify the upgrade path. '
               'Compatibility has not yet been confirmed for each unit.')
        if context['conflict']:
            reply+=' Support also needs to reconcile the earlier compatibility guidance against the actual hardware.'
        # A private security note alone must not introduce a customer-facing allegation.
        if context['security_review'] and re.search(r'(?i)\.exe|malware alert',public_text):
            reply+=' Your question about the detected executable also needs security review; its legitimacy has not been confirmed.'
        reply+=' No upgrade steps or cost estimate can be confirmed from the information currently verified.'
        return reply
    if support_action:
        return ('Thank you for the update. '+
                ('You reported that the controllers remain online without another occurrence. ' if context['currently_stable'] else '')+
                'The next step is for support to compare the other lane controllers’ temperatures and report the findings. '
                'That comparison is still pending, and the cause has not been confirmed. '
                'No further information is requested from you at this stage.')
    if context['remote_session_requested'] and context['waiting_for_customer']:
        reset=bool(re.search(r'(?i)reset|restablecer|reconfigur|configurar',ticket.description))
        if context['language']=='es':
            return ('Gracias por explicar la solicitud'+(' de restablecer y configurar la cámara. ' if reset else ' de soporte. ')+
                    'El siguiente paso es coordinar con soporte la sesión remota solicitada en nuestra respuesta anterior. '
                    'Falta confirmar un horario conveniente; la sesión aún no se ha realizado según la información revisada. '
                    'Antes de indicar cambios, soporte necesita comprobar el equipo y la configuración. '
                    'No envíe contraseñas ni códigos de acceso en este ticket.')
        return ('Thank you for explaining your request'+(' to reset and reconfigure the camera. ' if reset else ' for support. ')+
                'The next step is to coordinate the remote session requested in our previous reply. '
                'A suitable time still needs to be confirmed; the reviewed information does not establish that the session has taken place. '
                'Support needs to verify the device and configuration before recommending changes. '
                'Do not send passwords or access codes in this ticket.')
    return fallback
