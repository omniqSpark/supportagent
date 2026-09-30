"""Conservative normalization of explicit product fields, never ticket-text inference."""
import re


def map_product(custom, model_field='', version_field=''):
    notes=[]
    if model_field and model_field == version_field:
        return '', '', ['Product mapping conflict: model and version use the same field; both withheld.']
    def value(field, label):
        if not field:
            notes.append(label+' field is not configured; applicability is unverified.')
            return ''
        if not re.fullmatch(r'cf_[a-z0-9_]+',field):
            notes.append(label+' field name is invalid; value withheld.')
            return ''
        raw=custom.get(field)
        if raw is None or raw=='':
            notes.append(label+' field is empty or absent on this ticket.')
            return ''
        if not isinstance(raw,str) or len(raw)>100 or re.search(r'[\r\n;,|]',raw):
            notes.append(label+' field is not a single short text value; reviewer confirmation required.')
            return ''
        raw=raw.strip()
        if raw.casefold() in ('unknown','n/a','none','tbd','unconfirmed') or '[REDACTED]' in raw:
            notes.append(label+' is unconfirmed or redacted; value withheld.')
            return ''
        notes.append(label+' read from custom_fields.'+field+'; deployment accuracy still requires review.')
        return raw
    model=value(model_field,'Product model')
    version=value(version_field,'Product version')
    if version and not model:
        notes.append('Version without a product model cannot establish applicability; version withheld.')
        version=''
    return model,version,notes
