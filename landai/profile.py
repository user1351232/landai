"""자료 프로필: 수신 검사 결과를 JSON으로 남기고 이후 단계가 참조합니다."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

STATUS_ORDER = {"pass": 0, "warn": 1, "fail": 2}


@dataclass
class Check:
    rule: str
    status: str            # pass | warn | fail
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class DataProfile:
    dataset: str
    region: str
    files: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    checks: list[Check] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def add(self, rule: str, status: str, message: str, **details) -> Check:
        c = Check(rule, status, message, details)
        self.checks.append(c)
        return c

    @property
    def status(self) -> str:
        if not self.checks:
            return "pass"
        return max((c.status for c in self.checks), key=STATUS_ORDER.__getitem__)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status
        return d

    def save(self, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self.region}_{self.dataset}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
        return path

    def summary(self) -> str:
        mark = {"pass": "통과", "warn": "경고", "fail": "실패"}
        lines = [f"[{self.region}/{self.dataset}] 종합: {mark[self.status]}"]
        for c in self.checks:
            lines.append(f"  {mark[c.status]:<2}  {c.rule:<14} {c.message}")
        return "\n".join(lines)


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()
