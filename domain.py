"""Provider-neutral contract. Connectors return only these normalized fields."""
from dataclasses import dataclass, field, asdict
from typing import Protocol


@dataclass
class Conversation:
    body: str
    private: bool = False
    created_at: str = ""
    author_role: str = "unknown"


@dataclass
class Ticket:
    id: str
    subject: str
    description: str
    source: str = "sample"
    customer_id: str = ""
    site_id: str = ""
    customer_name: str = ""
    requester_name: str = ""
    site_name: str = ""
    assigned_agent: str = ""
    mapping_notes: str = ""
    identity_evidence: dict = field(default_factory=dict)
    product_model: str = ""
    product_version: str = ""
    priority: int = 2  # 1 low, 2 normal, 3 high, 4 urgent
    conversations: list[Conversation] = field(default_factory=list)
    history_complete: bool = True

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("Ticket must be an object")
        fields = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        if not isinstance(fields.get('identity_evidence',{}),dict):
            raise ValueError('Identity evidence must be an object')
        for key in ("id", "subject", "description"):
            if not isinstance(fields.get(key), str):
                raise ValueError("Ticket id, subject and description must be text")
        for key in ("customer_id", "site_id", "source", "customer_name", "requester_name", "site_name", "assigned_agent", "mapping_notes", "product_model", "product_version"):
            if key in fields and not isinstance(fields[key], str):
                raise ValueError("Identifiers must be text")
        if type(fields.get("priority", 2)) is not int or fields.get("priority", 2) not in (1, 2, 3, 4):
            raise ValueError("Priority must be 1–4")
        conv = fields.get("conversations", [])
        if not isinstance(conv, list) or len(conv) > 1000:
            raise ValueError("Invalid conversation history")
        for c in conv:
            if not isinstance(c, dict) or not isinstance(c.get("body"), str) or type(c.get("private", False)) is not bool:
                raise ValueError("Invalid conversation")
            if c.get('author_role', 'unknown') not in ('customer', 'support', 'unknown'):
                raise ValueError('Invalid conversation role')
        fields["conversations"] = [Conversation(c["body"], c.get("private", False), str(c.get("created_at", "")), c.get('author_role','unknown')) for c in conv]
        if type(fields.get("history_complete", True)) is not bool:
            raise ValueError("Invalid history flag")
        return cls(**fields)

    def to_dict(self):
        return asdict(self)


class TicketReader(Protocol):
    def list_tickets(self) -> list[dict]: ...
    def get_ticket(self, ticket_id: str) -> Ticket: ...
