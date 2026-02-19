"""Contract data model — deterministic criteria for bounty verification.

Contracts define "done" as executable criteria at creation time.
At verification, just run them — no AI judgment needed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class CriterionType(str, Enum):
    SHELL = "shell"  # Run command, check exit code
    CONTEXT_CHECK = "context_check"  # Check read-context JSON field
    FILE_EXISTS = "file_exists"  # Check file/dir exists
    GIT_CHECK = "git_check"  # Check git state


@dataclass
class Criterion:
    name: str
    type: CriterionType
    pass_when: str  # "exit_code == 0", "== 0", "not_empty"
    command: str | None = None  # Shell command (shell/git_check)
    field: str | None = None  # Context field (context_check)
    path: str | None = None  # File path (file_exists)
    weight: float = 1.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Criterion:
        data = dict(data)
        data["type"] = CriterionType(data["type"])
        return cls(**data)


@dataclass
class Contract:
    soul_purpose: str
    escrow: int
    criteria: list[Criterion] = field(default_factory=list)
    bounty_id: str = ""
    status: str = "draft"  # draft | active | submitted | verified | settled | forfeited

    def to_dict(self) -> dict:
        return {
            "soul_purpose": self.soul_purpose,
            "escrow": self.escrow,
            "criteria": [c.to_dict() for c in self.criteria],
            "bounty_id": self.bounty_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Contract:
        data = dict(data)
        data["criteria"] = [Criterion.from_dict(c) for c in data.get("criteria", [])]
        return cls(**data)

    def save(self, project_dir: str) -> Path:
        """Save contract to session-context/contract.json."""
        path = Path(project_dir) / "session-context" / "contract.json"
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    @classmethod
    def load(cls, project_dir: str) -> Contract | None:
        """Load contract from session-context/contract.json."""
        path = Path(project_dir) / "session-context" / "contract.json"
        if not path.is_file():
            return None
        try:
            return cls.from_dict(json.loads(path.read_text()))
        except Exception:
            return None
