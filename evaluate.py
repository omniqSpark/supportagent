"""Reproducible synthetic evaluation, explicitly not a field accuracy estimate."""
from pathlib import Path
from connectors import Samples, read_data
from engine import analyze


def main():
    fields=('category','technician','escalate','priority');correct={f:0 for f in fields}
    expected=read_data('expected.json');rows=[]
    for e in expected:
        r=analyze(Samples().get_ticket(e['id']),read_data('knowledge.json'),read_data('coverage.json'))
        for f in fields:correct[f]+=r[f]==e[f]
        rows.append(f"| {e['id']} | {r['category']} | {r['technician']} | {r['priority']} | {'Yes' if r['escalate'] else 'No'} | {'Pass' if all(r[f]==e[f] for f in fields) else 'FAIL'} |")
    report='# Sandbox evaluation\n\nSynthetic, authored fixtures; not held-out production evidence. Rules and cases were developed together. Correct routing includes appropriate abstention to Human dispatch.\n\n'
    report+='\n'.join(f'- {f}: {correct[f]}/{len(expected)} ({100*correct[f]/len(expected):.1f}%)' for f in fields)
    report+='\n\n| Ticket | Classification | Routing recommendation | Priority | Escalate | Result |\n|---|---|---|---|---|---|\n'+'\n'.join(rows)
    report+='\n\nLimitations: keyword matching does not reliably understand negation, chronology, synonyms, multilingual reports, or root cause. Historical incidents can over-escalate. No probability calibration. Urgent language can be missed outside the phrase list. Validate against an anonymized, independently labeled ticket set before relying on these scores. No real Freshdesk tenant was accessed.\n'
    Path(__file__).with_name('EVALUATION.md').write_text(report,encoding='utf-8')
    print(report)


if __name__=='__main__':main()
