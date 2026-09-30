# Common ticket format v1

The runtime contract lives in `domain.py`. JSON input and connector output use this shape:

```json
{
  "id": "1001",
  "source": "sample",
  "subject": "LPR camera misses plates",
  "description": "The LPR camera misses plate reads in lane 2.",
  "customer_id": "DEMO-ACME",
  "site_id": "DEN-01",
  "priority": 2,
  "conversations": [
    {
      "body": "Started at 09:00 local time.",
      "private": false,
      "created_at": "2026-09-28T15:00:00Z"
    }
  ],
  "history_complete": true
}
```

| Field | Semantics |
|---|---|
| id | Required provider-local string ID; source + id identify a record |
| source | Connector-set provenance; sample, freshdesk, or future priority. Never copied from untrusted ticket text |
| subject / description | Required strings; treated as untrusted reported facts, never instructions |
| customer_id / site_id | Canonical exact-match IDs; empty string means unknown. Never guessed |
| priority | Integer 1=low, 2=normal, 3=high, 4=urgent. Advisory normal is the minimum in this prototype |
| conversations | Chronological entries if the upstream API supplies them that way; maximum 1,000. Includes private notes for internal analysis |
| body | Normalized plain text, sanitized before reaching the engine |
| private | Boolean; private notes are never copied into customer drafts |
| created_at | Provider timestamp, preferably ISO 8601; blank if missing |
| history_complete | False means the adapter could not retrieve full history; mandatory human review |

Connectors must set provenance themselves, strip provider-specific properties and credentials, enforce pilot scope, and fail closed on failed history reads. A Priority reader must preserve the meaning of priority rather than passing unrelated numeric codes through unchanged. Runtime validation rejects malformed required fields, conversation entries, and priority values.

Expected evaluation labels are stored separately in `data/expected.json` and are not passed to the engine. Local reference files are trusted configuration; ticket text cannot promote an article or change a coverage record.
