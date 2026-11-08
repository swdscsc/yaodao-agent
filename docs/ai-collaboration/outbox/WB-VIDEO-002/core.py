"""WB-VIDEO-002 pipeline core.

Zero-paid-quota orchestration primitives for the Vidova -> editor -> QA pipeline:
  * VidovaMCP   : verified local MCP client (POST /mcp, JSON-RPC 2.0)
  * Manifest    : unique asset registry with dedupe
  * TaskStateMachine : bounded states + audited transitions
  * DefectLedger: repair-loop records
  * RetryPolicy : hard bounded retries and human-review gate

No credential, token, or machine-specific absolute path is embedded here.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

MCP_URL = "http://127.0.0.1:17373/mcp"
TZ = timezone(timedelta(hours=8))


def now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class MCPError(RuntimeError):
    pass


class VidovaMCP:
    """Client for the real Vidova local MCP endpoint (verified 2026-11-08)."""

    def __init__(self, url: str = MCP_URL, timeout: int = 40):
        self.url = url
        self.timeout = timeout
        self._id = 0
        self.call_log: list[dict] = []

    def _rpc(self, method: str, params: dict) -> dict:
        self._id += 1
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except Exception as exc:  # transport / timeout
            raise MCPError(f"transport {type(exc).__name__}: {exc}") from exc
        if raw.lstrip().startswith(("event:", "data:")):
            raw = "\n".join(
                line[5:].strip() for line in raw.splitlines() if line.startswith("data:")
            )
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MCPError(f"non-JSON response: {raw[:200]}") from exc
        if "error" in obj:
            raise MCPError(str(obj["error"]))
        return obj.get("result", {})

    def initialize(self) -> dict:
        return self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "wb-pipeline-e2e", "version": "1.0.0"},
            },
        )

    def list_tools(self) -> list[dict]:
        return self._rpc("tools/list", {}).get("tools", [])

    def call(self, name: str, arguments: dict | None = None) -> dict:
        arguments = arguments or {}
        started = time.time()
        try:
            result = self._rpc("tools/call", {"name": name, "arguments": arguments})
            texts = [
                c.get("text", "")
                for c in result.get("content", [])
                if isinstance(c, dict) and c.get("type") == "text"
            ]
            out = {
                "ok": not bool(result.get("isError")),
                "text": "\n".join(texts),
                "raw": result,
            }
        except MCPError as exc:
            out = {"ok": False, "text": "", "raw": None, "error": str(exc)}
        entry = {
            "ts": now(),
            "tool": name,
            "arguments": arguments,
            "ok": out["ok"],
            "response_excerpt": out.get("text", "")[:800],
            "elapsed_ms": int((time.time() - started) * 1000),
        }
        if "error" in out:
            entry["error"] = out["error"]
        self.call_log.append(entry)
        return out

    def save_log(self, path) -> None:
        Path(path).write_text(
            json.dumps(self.call_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Unified asset protocol
# ---------------------------------------------------------------------------

REQUIRED_ASSET_FIELDS = [
    "asset_id", "file_path", "file_type", "duration_seconds", "width", "height",
    "fps", "shot_id", "source_type", "is_ai_generated", "is_real_footage",
    "qa_status", "quality_checks", "allow_edit", "generation_status",
    "retry_count", "checksum_sha256", "notes",
]


class Manifest:
    """Unique-numbered asset registry. Dedupe key: (shot_id, source_type, sha256)."""

    def __init__(self, path, project_id: str):
        self.path = Path(path)
        self.project_id = project_id
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {
                "schema_version": "1.0",
                "project_id": project_id,
                "created_at": now(),
                "updated_at": now(),
                "dedupe_rule": "(shot_id, source_type, checksum_sha256)",
                "assets": [],
            }

    def _key(self, rec: dict):
        return (rec.get("shot_id"), rec.get("source_type"), rec.get("checksum_sha256"))

    def upsert(self, rec: dict) -> tuple[bool, str]:
        for field in REQUIRED_ASSET_FIELDS:
            if field not in rec:
                raise ValueError(f"manifest record missing required field: {field}")
        keys = [self._key(a) for a in self.data["assets"]]
        if self._key(rec) in keys:
            return False, "DUPLICATE_REJECTED"
        existing = [a for a in self.data["assets"] if a["asset_id"] == rec["asset_id"]]
        if existing:
            return False, "ASSET_ID_COLLISION"
        self.data["assets"].append(rec)
        self.data["updated_at"] = now()
        self.save()
        return True, "INSERTED"

    def patch(self, asset_id: str, updates: dict) -> None:
        for asset in self.data["assets"]:
            if asset["asset_id"] == asset_id:
                asset.update(updates)
                break
        else:
            raise KeyError(asset_id)
        self.data["updated_at"] = now()
        self.save()

    def approved(self) -> list[dict]:
        return [a for a in self.data["assets"] if a.get("allow_edit") is True]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Task state machine + bounded retry
# ---------------------------------------------------------------------------

STATES = {
    "PENDING", "GENERATING", "COMPLETED", "FAILED", "VALIDATING",
    "REVIEW_REQUIRED", "APPROVED", "EDITING", "EXPORTED",
    "QA_CHECKING", "DELIVERED", "ESCALATED",
}

ALLOWED = {
    "PENDING": {"GENERATING", "FAILED", "REVIEW_REQUIRED"},
    "GENERATING": {"COMPLETED", "FAILED", "REVIEW_REQUIRED"},
    "COMPLETED": {"VALIDATING", "FAILED"},
    "FAILED": {"PENDING", "ESCALATED", "REVIEW_REQUIRED"},
    "VALIDATING": {"APPROVED", "REVIEW_REQUIRED", "FAILED"},
    "REVIEW_REQUIRED": {"PENDING", "ESCALATED", "APPROVED"},
    "APPROVED": {"EDITING", "REVIEW_REQUIRED"},
    "EDITING": {"EXPORTED", "FAILED"},
    "EXPORTED": {"QA_CHECKING"},
    "QA_CHECKING": {"DELIVERED", "REVIEW_REQUIRED", "PENDING", "ESCALATED"},
    "DELIVERED": set(),
    "ESCALATED": set(),
}


class TaskStateMachine:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"states": {}, "transitions": [], "created_at": now()}

    def move(self, entity: str, to: str, note: str = "") -> None:
        if to not in STATES:
            raise ValueError(f"unknown state {to}")
        current = self.data["states"].get(entity, "PENDING")
        if to not in ALLOWED.get(current, set()):
            raise ValueError(f"illegal transition {current} -> {to} for {entity}")
        self.data["states"][entity] = to
        self.data["transitions"].append(
            {"ts": now(), "entity": entity, "from": current, "to": to, "note": note}
        )
        self.save()

    def state(self, entity: str) -> str:
        return self.data["states"].get(entity, "PENDING")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


class RetryPolicy:
    """Hard bounds. Production backoff is 5/15/45s; E2E can inject a fast profile."""

    MAX_GENERATION_ATTEMPTS = 3
    MAX_REWORK_CYCLES = 2
    POLL_TIMEOUT_SECONDS = 600
    HUMAN_REVIEW_GATE = "REVIEW_REQUIRED"

    def __init__(self, backoff=(5, 15, 45)):
        self.backoff = backoff
        self.attempts: dict[str, int] = {}
        self.cycles: dict[str, int] = {}

    def attempt(self, entity: str) -> int:
        self.attempts[entity] = self.attempts.get(entity, 0) + 1
        return self.attempts[entity]

    def can_retry(self, entity: str) -> bool:
        return self.attempts.get(entity, 0) < self.MAX_GENERATION_ATTEMPTS

    def wait(self, entity: str) -> float:
        n = min(self.attempts.get(entity, 1), len(self.backoff)) - 1
        delay = self.backoff[max(n, 0)]
        if delay:
            time.sleep(delay)
        return delay

    def cycle(self, entity: str) -> int:
        self.cycles[entity] = self.cycles.get(entity, 0) + 1
        return self.cycles[entity]

    def can_rework(self, entity: str) -> bool:
        return self.cycles.get(entity, 0) < self.MAX_REWORK_CYCLES


class DefectLedger:
    OWNER_ROUTES = {
        "asset": "vidova", "clip": "jianying", "audio": "audio_module",
        "subtitle": "subtitle_module", "render": "renderer",
    }

    def __init__(self, path):
        self.path = Path(path)
        self.data = (
            json.loads(self.path.read_text(encoding="utf-8"))
            if self.path.exists()
            else {"defects": [], "max_rework_cycles": 2, "created_at": now()}
        )

    def add(self, defect_id, timecode, description, severity, category,
            owner_module, fix_plan, asset_id=None) -> dict:
        rec = {
            "defect_id": defect_id,
            "timecode": timecode,
            "description": description,
            "severity": severity,
            "category": category,
            "owner_module": owner_module or self.OWNER_ROUTES.get(category, "unknown"),
            "asset_id": asset_id,
            "fix_plan": fix_plan,
            "fix_result": "OPEN",
            "retry_count": 0,
            "created_at": now(),
            "resolved_at": None,
        }
        self.data["defects"].append(rec)
        self.save()
        return rec

    def resolve(self, defect_id, result: str, retry_count: int = 0) -> None:
        for d in self.data["defects"]:
            if d["defect_id"] == defect_id:
                d["fix_result"] = result
                d["retry_count"] = retry_count
                d["resolved_at"] = now()
                break
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
