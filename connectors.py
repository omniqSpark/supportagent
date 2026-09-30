"""Read-only adapters. Freshdesk authorization is confined to the HTTPS transport."""
import base64
import html
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from domain import Ticket
from product_mapping import map_product
from identity_resolution import resolve as resolve_identity, apply_display_confirmation

ROOT = Path(__file__).parent


class SafeError(Exception):
    """Only fixed, non-sensitive messages cross the HTTP boundary."""


def load_env(path=ROOT / ".env"):
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def scrub(value, secret=""):
    """Defense in depth: redact configured secret and common credential forms at ingress."""
    if isinstance(value, dict):
        return {k: scrub(v, secret) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, secret) for v in value]
    if not isinstance(value, str):
        return value
    if secret:
        for variant in (secret, quote(secret, safe=""), base64.b64encode((secret + ":X").encode()).decode()):
            value = value.replace(variant, "[REDACTED]")
    value = re.sub(r"(?i)\b(password|passwd|api[_ -]?key|token|secret|authorization)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value)
    return re.sub(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9+/=._-]+", "[REDACTED]", value)


def read_data(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


class Samples:
    def list_tickets(self):
        return [{"id": t["id"], "subject": t["subject"]} for t in read_data("tickets.json")]

    def get_ticket(self, ticket_id):
        for item in read_data("tickets.json"):
            if item["id"] == ticket_id:
                data = scrub(item, os.environ.get("FRESHDESK_API_KEY", ""))
                data["source"] = "sample"
                return Ticket.from_dict(data)
        raise SafeError("Ticket not found in sample set")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafeError("Freshdesk redirect blocked")


class Freshdesk:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        domain = env.get("FRESHDESK_DOMAIN", "")
        key = env.get("FRESHDESK_API_KEY", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.freshdesk\.com", domain) or not key or key == "replace-locally":
            raise SafeError("Freshdesk configuration is missing or invalid. Check local environment settings.")
        ids = env.get("FRESHDESK_TICKET_IDS", "").strip()
        group = env.get("FRESHDESK_GROUP_ID", "").strip()
        if ids and not re.fullmatch(r"[1-9]\d*(\s*,\s*[1-9]\d*)*", ids):
            raise SafeError("Pilot ticket IDs must be positive integers")
        if group and not re.fullmatch(r"[1-9]\d*", group):
            raise SafeError("Pilot group ID must be a positive integer")
        if not ids and not group:
            raise SafeError("Freshdesk requires a ticket allowlist or test group")
        self._domain, self._key = domain, key
        self.ids = set(ids.replace(" ", "").split(",")) if ids else set()
        if len(self.ids) > 100:
            raise SafeError("Limit pilot allowlist to 100 tickets")
        self.group = int(group) if group else None
        self.customer_field = env.get("FRESHDESK_CUSTOMER_FIELD", "company_id")
        self.site_field = env.get("FRESHDESK_SITE_FIELD", "cf_location")
        self.model_field = env.get('FRESHDESK_MODEL_FIELD', '')
        self.version_field = env.get('FRESHDESK_VERSION_FIELD', '')
        self._opener = build_opener(NoRedirect(), ProxyHandler({}))

    def _get(self, path):
        if not re.fullmatch(r"/api/v2/(solutions/(categories|categories/[1-9]\d*/folders|folders/[1-9]\d*/(?:articles|subfolders))(?:\?page=[1-9]\d*&per_page=100)?|ticket_fields|contacts/[1-9]\d*|companies(?:\?per_page=100&page=[1-9]\d*)?|companies/[1-9]\d*|agents/[1-9]\d*|tickets/[1-9]\d*(/conversations\?per_page=100&page=[1-9]\d*)?|search/tickets\?.+)", path):
            raise SafeError("Connector endpoint blocked")
        auth = base64.b64encode((self._key + ":X").encode()).decode()
        request = Request("https://" + self._domain + path, headers={"Authorization": "Basic " + auth, "Accept": "application/json"}, method="GET")
        try:
            with self._opener.open(request, timeout=20) as response:
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise SafeError("Freshdesk response exceeds sandbox limit")
                return scrub(json.loads(raw), self._key)
        except HTTPError as exc:
            messages = {401: "Freshdesk authentication failed", 403: "Freshdesk access denied", 404: "Freshdesk ticket not found", 429: "Freshdesk rate limit reached. Wait before retrying."}
            raise SafeError(messages.get(exc.code, "Freshdesk request failed; retry later")) from None
        except (URLError, TimeoutError, ValueError, OSError):
            raise SafeError("Freshdesk read failed. Check connectivity and configuration.") from None

    def _group_ids(self):
        found = []
        for page in range(1, 11):
            result = self._get("/api/v2/search/tickets?" + urlencode({"query": f'"group_id:{self.group}"', "page": page}))
            if result.get("total", 0) > 300:
                raise SafeError("Test group exceeds 300-ticket pilot limit. Use a smaller group or explicit IDs.")
            rows = result.get("results", [])
            found.extend(str(t["id"]) for t in rows if t.get("group_id") == self.group)
            if page * 30 >= result.get("total", 0):
                return found
        raise SafeError("Test group listing incomplete; narrow the pilot scope")

    def list_tickets(self):
        # Do not prefetch bodies. Group search is server-filtered; titles remain generic.
        ids = sorted(self.ids, key=int) if self.ids else self._group_ids()
        return [{"id": i, "subject": "Freshdesk ticket " + i} for i in ids]

    def get_ticket(self, ticket_id):
        if not re.fullmatch(r"[1-9]\d*", ticket_id):
            raise SafeError("Invalid ticket ID")
        if self.ids and ticket_id not in self.ids:
            raise SafeError("Ticket is outside the pilot allowlist")
        if self.group and not self.ids and ticket_id not in self._group_ids():
            raise SafeError("Ticket is outside the pilot group")
        raw = self._get("/api/v2/tickets/" + ticket_id)
        # Recheck actual group: search indexes can lag behind reassignment.
        if self.group and raw.get("group_id") != self.group:
            raise SafeError("Ticket is outside the pilot group")
        conversations, complete = [], False
        roles = {}
        for page in range(1, 11):
            rows = self._get(f"/api/v2/tickets/{ticket_id}/conversations?per_page=100&page={page}")
            for entry in rows:
                uid = str(entry.get('user_id') or '')
                role = self._role(entry, raw)
                if role == 'unknown' and entry.get('incoming') is False and re.fullmatch(r'[1-9]\d*',uid):
                    if uid not in roles and len(roles) < 20:
                        try:
                            agent = self._get('/api/v2/agents/'+uid)
                            roles[uid] = 'support' if str(agent.get('id')) == uid else 'unknown'
                        except SafeError:
                            roles[uid] = 'unknown'
                    role = roles.get(uid, 'unknown')
                entry['_mapped_role'] = role
            conversations.extend({"body": self._text(c.get("body_text") or c.get("body") or ""),
                                  "private": bool(c.get("private")), "created_at": c.get("created_at") or "",
                                  "author_role": c['_mapped_role']} for c in rows)
            if len(rows) < 100:
                complete = True
                break
        custom = raw.get("custom_fields") or {}
        customer_id = str(raw.get("company_id") or "") if self.customer_field == "company_id" else str(custom.get(self.customer_field) or "")
        site_id = str(custom.get(self.site_field) or "")
        customer_name, assigned_agent = "", ""
        notes = [f"Customer: {self.customer_field}; site: custom_fields.{self.site_field}."]
        # Resolve only records linked to this scope-checked ticket; never list the directory.
        for field, endpoint in (("company_id", "companies"), ("responder_id", "agents")):
            linked_id = str(raw.get(field) or "")
            if not re.fullmatch(r"[1-9]\d*", linked_id):
                continue
            try:
                linked = self._get(f"/api/v2/{endpoint}/{linked_id}")
                if endpoint == "companies" and self.customer_field == "company_id":
                    customer_name = self._text(linked.get("name") or "")
                if endpoint == "agents":
                    assigned_agent = self._text((linked.get("contact") or {}).get("name") or linked.get("name") or "")
            except SafeError:
                notes.append(f"Linked {endpoint} lookup unavailable; no name inferred.")
        notes.append("Assigned agent is ticket ownership only; technician coverage and skills require approved records.")
        contact={}
        requester_id=str(raw.get('requester_id') or '')
        if re.fullmatch(r'[1-9]\d*',requester_id):
            try:
                contact=self._get('/api/v2/contacts/'+requester_id)
            except SafeError:
                notes.append('Requester contact lookup unavailable; identity remains unverified.')
        try:
            directory=json.loads((ROOT/'local_reviews/company_directory.json').read_text(encoding='utf-8'))['companies']
        except (OSError,ValueError,KeyError):
            directory=[]
        identity_evidence=resolve_identity(raw.get('company_id'),contact,directory,site_id)
        customer_name=apply_display_confirmation(ticket_id,identity_evidence,customer_name)
        model, version, product_notes = map_product(custom, self.model_field, self.version_field)
        notes.extend(product_notes)
        return Ticket.from_dict(dict(id=ticket_id, source="freshdesk", subject=self._text(raw.get("subject") or ""),
            description=self._text(raw.get("description_text") or raw.get("description") or ""),
            customer_id=customer_id, site_id=site_id, customer_name=customer_name,
            requester_name=self._text(contact.get("name") or ""),
            site_name=site_id, assigned_agent=assigned_agent, mapping_notes=" ".join(notes),
            identity_evidence=identity_evidence,
            product_model=model, product_version=version,
            priority=raw.get("priority", 2), conversations=conversations, history_complete=complete))

    def _text(self, value):
        return scrub(html.unescape(re.sub(r"<[^>]*>", " ", str(value))), self._key)

    @staticmethod
    def _role(conversation, ticket):
        user = conversation.get('user_id')
        if user and user == ticket.get('requester_id'):
            return 'customer'
        if user and user == ticket.get('responder_id'):
            return 'support'
        # Direction alone is not reliable proof of agent identity (portal notes).
        return 'unknown'
