from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Lead:
    lead_id: str
    first_name: str = ""
    last_name: str = ""
    job_title: str = ""
    company: str = ""
    website_url: str = ""
    phone: str = ""
    email: str = ""
    linkedin_url: str = ""
    location: str = ""
    industry: str = ""

    @property
    def contact_name(self) -> str:
        return " ".join(x for x in [self.first_name, self.last_name] if x).strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Issue:
    category: str
    level: str
    title: str
    fix: str
    points: int
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditRecord:
    lead: Lead
    checks: dict[str, Any] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "lead": self.lead.to_dict(),
            "checks": self.checks,
            "issues": [x.to_dict() for x in self.issues],
            "scores": self.scores,
            "errors": self.errors,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
        }
